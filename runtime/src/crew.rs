//! Crew panes: the visible grid panes the wall drives through
//! `pane create --crew`, `pane grid` and `pane list --crew`.

use std::collections::HashMap;
use std::time::Instant;

use crate::app::App;
use crate::layout::PaneId;
use crate::terminal::TerminalState;

pub const CREW_ROLE: &str = "crew";

pub fn is_crew_role(role: &str) -> bool {
    role.eq_ignore_ascii_case(CREW_ROLE)
}

pub fn visible_crew_pane_ids(app: &App, ws_idx: usize, tab_idx: usize) -> Vec<PaneId> {
    app.state
        .workspaces
        .get(ws_idx)
        .and_then(|ws| ws.tabs.get(tab_idx))
        .map(|tab| tab.layout.pane_ids())
        .unwrap_or_default()
}

/// The pane a new crew pane splits from: the focused pane of the active tab,
/// else the last pane in the layout.
pub fn resolve_crew_split_target(
    app: &App,
    workspace_idx: Option<usize>,
) -> Option<(usize, usize, PaneId)> {
    let ws_idx = workspace_idx.or(app.state.active)?;
    let ws = app.state.workspaces.get(ws_idx)?;
    let tab_idx = ws.active_tab;
    let tab = ws.tabs.get(tab_idx)?;
    let focused = tab.layout.focused();
    if tab.layout.pane_ids().contains(&focused) {
        return Some((ws_idx, tab_idx, focused));
    }
    tab.layout
        .pane_ids()
        .last()
        .copied()
        .map(|pane_id| (ws_idx, tab_idx, pane_id))
}

/// A plain shell that nothing has claimed yet. The first `pane create --crew`
/// adopts it instead of splitting it.
pub fn unused_grid_shell(app: &App, ws_idx: usize, pane_id: PaneId) -> bool {
    let Some(ws) = app.state.workspaces.get(ws_idx) else {
        return false;
    };
    let Some(pane) = ws.pane_state(pane_id) else {
        return false;
    };
    let Some(terminal) = app.state.terminals.get(&pane.attached_terminal_id) else {
        return true;
    };
    if terminal
        .launch_argv
        .as_ref()
        .is_some_and(|argv| !argv.is_empty())
    {
        return false;
    }
    if terminal
        .metadata_tokens
        .values()
        .get("role")
        .is_some_and(|role| is_crew_role(role))
    {
        return false;
    }
    terminal.effective_agent_label().is_none()
}

pub fn stamp_crew(terminal: &mut TerminalState, bind: Option<&str>) {
    let mut patch = HashMap::from([("role".to_string(), Some(CREW_ROLE.to_string()))]);
    if let Some(bind) = bind.map(str::trim).filter(|bind| !bind.is_empty()) {
        terminal.set_manual_label(bind.to_string());
        patch.insert("bind".to_string(), Some(bind.to_string()));
    }
    terminal.metadata_tokens.patch(patch, None, Instant::now());
}

pub fn bind_crew_alias(app: &mut App, pane_id: PaneId, bind: &str) {
    let bind = bind.trim();
    if bind.is_empty() {
        return;
    }
    app.state
        .public_pane_id_aliases
        .insert(bind.to_string(), pane_id);
}

pub fn crew_grid_node(panes: &[PaneId], kind: u8) -> Option<crate::layout::Node> {
    if panes.is_empty() {
        return None;
    }
    Some(match kind {
        4 => two_by_two_tree(panes),
        _ => column_tree(panes),
    })
}

fn column_tree(panes: &[PaneId]) -> crate::layout::Node {
    match panes {
        [] => unreachable!("column_tree requires at least one pane"),
        [pane] => crate::layout::Node::Pane(*pane),
        [first, rest @ ..] => crate::layout::Node::Split {
            direction: ratatui::layout::Direction::Horizontal,
            ratio: 1.0 / panes.len() as f32,
            first: Box::new(crate::layout::Node::Pane(*first)),
            second: Box::new(column_tree(rest)),
        },
    }
}

fn two_by_two_tree(panes: &[PaneId]) -> crate::layout::Node {
    if panes.len() <= 2 {
        return column_tree(panes);
    }
    let split_at = 2.min(panes.len());
    crate::layout::Node::Split {
        direction: ratatui::layout::Direction::Vertical,
        ratio: 0.5,
        first: Box::new(column_tree(&panes[..split_at])),
        second: Box::new(column_tree(&panes[split_at..])),
    }
}

pub fn apply_crew_grid_layout(
    app: &mut App,
    ws_idx: usize,
    tab_idx: usize,
    kind: u8,
) -> Result<(), String> {
    let crew = visible_crew_pane_ids(app, ws_idx, tab_idx);
    if crew.is_empty() {
        return Err("no crew panes".into());
    }
    let node = crew_grid_node(&crew, kind).ok_or("empty crew grid")?;
    let current_focus = app
        .state
        .workspaces
        .get(ws_idx)
        .and_then(|ws| ws.tabs.get(tab_idx))
        .map(|tab| tab.layout.focused());
    let focus = current_focus
        .filter(|pane_id| crew.contains(pane_id))
        .unwrap_or(crew[0]);
    let Some(tab) = app
        .state
        .workspaces
        .get_mut(ws_idx)
        .and_then(|ws| ws.tabs.get_mut(tab_idx))
    else {
        return Err("tab not found".into());
    };
    tab.root_pane = node.first_pane();
    tab.layout = crate::layout::TileLayout::from_saved(node, focus);
    tab.zoomed = false;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::api::schema::{
        Method, PaneCreateParams, PaneGridParams, PaneListParams, Request, SuccessResponse,
    };
    use crate::config::Config;
    use crate::workspace::Workspace;
    use ratatui::layout::Rect;

    fn test_app() -> App {
        let (_api_tx, api_rx) = tokio::sync::mpsc::unbounded_channel();
        let mut app = App::new(
            &Config::default(),
            true,
            None,
            api_rx,
            crate::api::EventHub::default(),
        );
        app.state.workspaces.push(Workspace::test_new("grid"));
        app.state.active = Some(0);
        app.state.mode = crate::app::Mode::Terminal;
        app.state.ensure_test_terminals();
        app
    }

    fn create_crew(app: &mut App, id: &str, bind: &str) -> crate::api::schema::PaneInfo {
        let created = app.handle_api_request(Request {
            id: id.into(),
            method: Method::PaneCreate(PaneCreateParams {
                crew: true,
                bind: Some(bind.into()),
                ..Default::default()
            }),
        });
        let success: SuccessResponse = serde_json::from_str(&created).unwrap();
        let crate::api::schema::ResponseResult::PaneInfo { pane } = success.result else {
            panic!("expected pane info, got {success:?}");
        };
        pane
    }

    #[test]
    fn grid_node_shapes_follow_the_count() {
        let panes: Vec<PaneId> = (0..4).map(|_| PaneId::alloc()).collect();
        assert!(crew_grid_node(&[], 2).is_none());
        assert_eq!(
            crew_grid_node(&panes[..1], 2).unwrap().first_pane(),
            panes[0]
        );
        let three = crew_grid_node(&panes[..3], 3).unwrap();
        assert_eq!(three.first_pane(), panes[0]);
        let crate::layout::Node::Split { direction, .. } = three else {
            panic!("three panes split");
        };
        assert_eq!(direction, ratatui::layout::Direction::Horizontal);
        let four = crew_grid_node(&panes, 4).unwrap();
        let crate::layout::Node::Split { direction, .. } = four else {
            panic!("four panes split");
        };
        assert_eq!(direction, ratatui::layout::Direction::Vertical);
    }

    #[tokio::test]
    async fn first_crew_pane_adopts_the_unused_shell_and_the_next_one_splits() {
        let mut app = test_app();
        let root = app.state.workspaces[0].tabs[0].root_pane;
        assert!(unused_grid_shell(&app, 0, root));

        let first = create_crew(&mut app, "create-crew-0", "body0");
        assert_eq!(first.label.as_deref(), Some("body0"));
        assert_eq!(
            app.parse_pane_id("body0").map(|(_, id)| id),
            Some(root),
            "the first crew pane adopts the workspace shell"
        );
        assert_eq!(app.state.workspaces[0].tabs[0].layout.pane_count(), 1);
        assert!(!unused_grid_shell(&app, 0, root));

        let second = create_crew(&mut app, "create-crew-1", "body1");
        assert_ne!(second.pane_id, first.pane_id);
        assert_eq!(app.state.workspaces[0].tabs[0].layout.pane_count(), 2);
        let second_id = app.parse_pane_id("body1").map(|(_, id)| id).unwrap();
        assert!(app.state.workspaces[0].tabs[0]
            .layout
            .pane_ids()
            .contains(&second_id));

        let listed = app.handle_api_request(Request {
            id: "list-crew".into(),
            method: Method::PaneList(PaneListParams {
                workspace_id: None,
                crew: true,
            }),
        });
        let listed: SuccessResponse = serde_json::from_str(&listed).unwrap();
        let crate::api::schema::ResponseResult::PaneList { panes } = listed.result else {
            panic!("expected pane list");
        };
        assert_eq!(panes.len(), 2);
        assert!(panes
            .iter()
            .all(|pane| pane.tokens.get("role").map(String::as_str) == Some(CREW_ROLE)));
    }

    #[tokio::test]
    async fn grid_fills_and_lays_out_crew_panes() {
        let mut app = test_app();
        let grid = app.handle_api_request(Request {
            id: "grid-3".into(),
            method: Method::PaneGrid(PaneGridParams {
                count: 3,
                workspace_id: None,
                tab_id: None,
            }),
        });
        let grid: SuccessResponse = serde_json::from_str(&grid).unwrap();
        let crate::api::schema::ResponseResult::LayoutApply { .. } = grid.result else {
            panic!("expected layout apply, got {grid:?}");
        };
        let tab = &app.state.workspaces[0].tabs[0];
        assert_eq!(tab.layout.pane_count(), 3);
        let rects = tab.layout.panes(Rect::new(0, 0, 90, 24));
        assert_eq!(rects.len(), 3);
        assert!(rects.iter().all(|info| info.rect.y == 0), "3 up is one row");
    }
}
