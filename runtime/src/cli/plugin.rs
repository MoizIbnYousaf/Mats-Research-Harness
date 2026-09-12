use std::collections::HashMap;
use std::io;
use std::path::{Path, PathBuf};

use crate::api::schema::{
    InstalledPluginInfo, Method, PluginActionInvokeParams, PluginActionListParams,
    PluginInvocationContext, PluginLinkParams, PluginListParams, PluginLogListParams,
    PluginPaneCloseParams, PluginPaneFocusParams, PluginPaneOpenParams, PluginPanePlacement,
    PluginSetEnabledParams, PluginSourceKind, PluginUnlinkParams, Request, ResponseResult,
    SplitDirection, SuccessResponse,
};
use crate::popup_size::PopupSize;

pub(super) fn run_plugin_command(args: &[String]) -> std::io::Result<i32> {
    let Some(subcommand) = args.first().map(|arg| arg.as_str()) else {
        print_plugin_help();
        return Ok(2);
    };

    match subcommand {
        "uninstall" => plugin_uninstall(&args[1..]),
        "link" => plugin_link(&args[1..]),
        "list" => plugin_list(&args[1..]),
        "config-dir" => plugin_config_dir_command(&args[1..]),
        "unlink" => plugin_unlink(&args[1..]),
        "enable" => plugin_set_enabled(&args[1..], true),
        "disable" => plugin_set_enabled(&args[1..], false),
        "action" => run_plugin_action_command(&args[1..]),
        "log" | "logs" => plugin_log_list(&args[1..]),
        "pane" => run_plugin_pane_command(&args[1..]),
        "help" | "--help" | "-h" => {
            print_plugin_help();
            Ok(0)
        }
        _ => {
            print_plugin_help();
            Ok(2)
        }
    }
}

fn plugin_link(args: &[String]) -> std::io::Result<i32> {
    let Some(path) = args.first() else {
        eprintln!(
            "{}",
            crate::identity::usage("plugin link <path> [--disabled]")
        );
        return Ok(2);
    };
    let path = normalize_plugin_path_arg(path)?;
    let mut enabled = true;
    let mut index = 1;
    while index < args.len() {
        match args[index].as_str() {
            "--disabled" => {
                enabled = false;
                index += 1;
            }
            "--enabled" => {
                enabled = true;
                index += 1;
            }
            other => {
                eprintln!("unknown option: {other}");
                return Ok(2);
            }
        }
    }
    let params = PluginLinkParams {
        path,
        enabled,
        source: None,
    };
    let response = match super::send_request(&Request {
        id: "cli:plugin".into(),
        method: Method::PluginLink(params.clone()),
    }) {
        Ok(response) => response,
        Err(err) if is_connection_error(&err) => offline_plugin_link_response(&params)?,
        Err(err) => return Err(err),
    };
    super::print_response(&response)
}

fn plugin_config_dir_command(args: &[String]) -> std::io::Result<i32> {
    let Some(plugin_id) = args.first() else {
        eprintln!(
            "{}",
            crate::identity::usage("plugin config-dir <plugin_id>")
        );
        return Ok(2);
    };
    if args.len() != 1 {
        eprintln!(
            "{}",
            crate::identity::usage("plugin config-dir <plugin_id>")
        );
        return Ok(2);
    }
    let path = crate::plugin_paths::plugin_config_dir(plugin_id);
    crate::plugin_paths::ensure_plugin_user_dirs(plugin_id)?;
    println!("{}", path.display());
    Ok(0)
}

fn plugin_list(args: &[String]) -> std::io::Result<i32> {
    let mut plugin_id = None;
    let mut json = false;
    let mut index = 0;
    while index < args.len() {
        match args[index].as_str() {
            "--json" => {
                json = true;
                index += 1;
            }
            "--plugin" => {
                let Some(value) = required_value(args, &mut index, "--plugin") else {
                    return Ok(2);
                };
                plugin_id = Some(value);
            }
            other => {
                eprintln!("unknown option: {other}");
                return Ok(2);
            }
        }
    }
    let params = PluginListParams { plugin_id };
    let response = match super::send_request(&Request {
        id: "cli:plugin".into(),
        method: Method::PluginList(params.clone()),
    }) {
        Ok(response) => response,
        Err(err) if is_connection_error(&err) => offline_plugin_list_response(&params)?,
        Err(err) => return Err(err),
    };
    if json {
        return super::print_response(&response);
    }
    print_plugin_list_human(&response)
}

fn plugin_unlink(args: &[String]) -> std::io::Result<i32> {
    let Some(plugin_id) = args.first() else {
        eprintln!("{}", crate::identity::usage("plugin unlink <plugin_id>"));
        return Ok(2);
    };
    if args.len() != 1 {
        eprintln!("{}", crate::identity::usage("plugin unlink <plugin_id>"));
        return Ok(2);
    }
    print_plugin_response(Method::PluginUnlink(PluginUnlinkParams {
        plugin_id: plugin_id.clone(),
    }))
}

fn plugin_uninstall(args: &[String]) -> std::io::Result<i32> {
    let Some(target) = args.first() else {
        eprintln!(
            "{}",
            crate::identity::usage("plugin uninstall <plugin_id|owner/repo[/subdir...]>")
        );
        return Ok(2);
    };
    if args.len() != 1 {
        eprintln!(
            "{}",
            crate::identity::usage("plugin uninstall <plugin_id|owner/repo[/subdir...]>")
        );
        return Ok(2);
    }

    let (plugin_id, existing) = match GithubPluginSource::parse(target) {
        Ok(source) => {
            let existing = installed_plugin_by_github_source(&source)?;
            let Some(existing) = existing else {
                eprintln!("plugin not installed: {}", source.display());
                return Ok(1);
            };
            (existing.plugin_id.clone(), Some(existing))
        }
        Err(_) => {
            let existing = match live_installed_plugin_info(target) {
                Ok(plugin) => plugin,
                Err(err) if is_connection_error(&err) => registry_plugin_info(target),
                Err(err) => return Err(err),
            };
            (target.clone(), existing)
        }
    };

    match super::send_request(&Request {
        id: "cli:plugin".into(),
        method: Method::PluginUnlink(PluginUnlinkParams {
            plugin_id: plugin_id.clone(),
        }),
    }) {
        Ok(response) => {
            if response.get("error").is_some() {
                return super::print_response(&response);
            }
            if response["result"]["removed"].as_bool() == Some(false) {
                eprintln!("plugin not installed: {target}");
                return Ok(1);
            }
        }
        Err(err) if is_connection_error(&err) => {
            let (removed, _) = crate::persist::plugin_registry::update(|plugins| {
                let before = plugins.len();
                plugins.retain(|plugin| plugin.plugin_id != plugin_id);
                before != plugins.len()
            })?;
            if !removed {
                eprintln!("plugin not installed: {target}");
                return Ok(1);
            }
        }
        Err(err) => return Err(err),
    }

    if let Some(plugin) = existing.as_ref() {
        remove_managed_plugin_files(plugin)?;
    }
    println!("Uninstalled {plugin_id}.");
    Ok(0)
}

fn plugin_set_enabled(args: &[String], enabled: bool) -> std::io::Result<i32> {
    let Some(plugin_id) = args.first() else {
        eprintln!(
            "usage: {} plugin {} <plugin_id>",
            crate::identity::help_usage_name(),
            if enabled { "enable" } else { "disable" }
        );
        return Ok(2);
    };
    if args.len() != 1 {
        eprintln!(
            "usage: {} plugin {} <plugin_id>",
            crate::identity::help_usage_name(),
            if enabled { "enable" } else { "disable" }
        );
        return Ok(2);
    }
    let params = PluginSetEnabledParams {
        plugin_id: plugin_id.clone(),
    };
    if enabled {
        print_plugin_response(Method::PluginEnable(params))
    } else {
        print_plugin_response(Method::PluginDisable(params))
    }
}

fn plugin_log_list(args: &[String]) -> std::io::Result<i32> {
    let mut plugin_id = None;
    let mut limit = None;
    let mut index = 0;
    while index < args.len() {
        match args[index].as_str() {
            "list" if index == 0 => index += 1,
            "--plugin" => {
                let Some(value) = required_value(args, &mut index, "--plugin") else {
                    return Ok(2);
                };
                plugin_id = Some(value);
            }
            "--limit" => {
                let Some(raw) = required_value(args, &mut index, "--limit") else {
                    return Ok(2);
                };
                let Ok(parsed) = raw.parse::<usize>() else {
                    eprintln!("invalid --limit value: {raw}");
                    return Ok(2);
                };
                limit = Some(parsed);
            }
            other => {
                eprintln!("unknown option: {other}");
                return Ok(2);
            }
        }
    }
    print_plugin_response(Method::PluginLogList(PluginLogListParams {
        plugin_id,
        limit,
    }))
}

fn run_plugin_action_command(args: &[String]) -> std::io::Result<i32> {
    let Some(subcommand) = args.first().map(|arg| arg.as_str()) else {
        print_plugin_action_help();
        return Ok(2);
    };

    match subcommand {
        "list" => plugin_action_list(&args[1..]),
        "invoke" => plugin_action_invoke(&args[1..]),
        "help" | "--help" | "-h" => {
            print_plugin_action_help();
            Ok(0)
        }
        _ => {
            print_plugin_action_help();
            Ok(2)
        }
    }
}

fn plugin_action_list(args: &[String]) -> std::io::Result<i32> {
    let mut plugin_id = None;
    let mut index = 0;
    while index < args.len() {
        match args[index].as_str() {
            "--plugin" => {
                let Some(value) = required_value(args, &mut index, "--plugin") else {
                    return Ok(2);
                };
                plugin_id = Some(value);
            }
            other => {
                eprintln!("unknown option: {other}");
                return Ok(2);
            }
        }
    }

    print_plugin_response(Method::PluginActionList(PluginActionListParams {
        plugin_id,
    }))
}

fn plugin_action_invoke(args: &[String]) -> std::io::Result<i32> {
    let Some(action_id) = args.first() else {
        eprintln!(
            "{}",
            crate::identity::usage("plugin action invoke <action_id> [--plugin ID]")
        );
        return Ok(2);
    };
    let mut plugin_id = None;
    let mut index = 1;
    while index < args.len() {
        match args[index].as_str() {
            "--plugin" => {
                let Some(value) = required_value(args, &mut index, "--plugin") else {
                    return Ok(2);
                };
                plugin_id = Some(value);
            }
            other => {
                eprintln!("unknown option: {other}");
                return Ok(2);
            }
        }
    }

    print_plugin_response(Method::PluginActionInvoke(PluginActionInvokeParams {
        action_id: action_id.clone(),
        plugin_id,
        context: Some(PluginInvocationContext {
            workspace_id: None,
            workspace_label: None,
            workspace_cwd: None,
            worktree: None,
            tab_id: None,
            tab_label: None,
            focused_pane_id: None,
            focused_pane_cwd: None,
            focused_pane_agent: None,
            focused_pane_status: None,
            selected_text: None,
            invocation_source: Some("cli".into()),
            correlation_id: None,
            clicked_url: None,
            link_handler_id: None,
        }),
    }))
}

fn run_plugin_pane_command(args: &[String]) -> std::io::Result<i32> {
    let Some(subcommand) = args.first().map(|arg| arg.as_str()) else {
        print_plugin_pane_help();
        return Ok(2);
    };

    match subcommand {
        "open" => plugin_pane_open(&args[1..]),
        "focus" => plugin_pane_focus(&args[1..]),
        "close" => plugin_pane_close(&args[1..]),
        "help" | "--help" | "-h" => {
            print_plugin_pane_help();
            Ok(0)
        }
        _ => {
            print_plugin_pane_help();
            Ok(2)
        }
    }
}

fn plugin_pane_open(args: &[String]) -> std::io::Result<i32> {
    let mut plugin_id = None;
    let mut entrypoint = None;
    let mut placement = None;
    let mut width = None;
    let mut height = None;
    let mut workspace_id = None;
    let mut target_pane_id = None;
    let mut direction = None;
    let mut cwd = None;
    let mut focus = true;
    let mut env = HashMap::new();

    let mut index = 0;
    while index < args.len() {
        match args[index].as_str() {
            "--plugin" => {
                let Some(value) = required_value(args, &mut index, "--plugin") else {
                    return Ok(2);
                };
                plugin_id = Some(value);
            }
            "--entrypoint" => {
                let Some(value) = required_value(args, &mut index, "--entrypoint") else {
                    return Ok(2);
                };
                entrypoint = Some(value);
            }
            "--placement" => {
                let Some(value) = required_value(args, &mut index, "--placement") else {
                    return Ok(2);
                };
                let Some(parsed) = parse_pane_placement(&value) else {
                    return Ok(2);
                };
                placement = Some(parsed);
            }
            "--width" => {
                let Some(value) = required_value(args, &mut index, "--width") else {
                    return Ok(2);
                };
                let Some(parsed) = parse_popup_dimension(&value, "--width") else {
                    return Ok(2);
                };
                width = Some(parsed);
            }
            "--height" => {
                let Some(value) = required_value(args, &mut index, "--height") else {
                    return Ok(2);
                };
                let Some(parsed) = parse_popup_dimension(&value, "--height") else {
                    return Ok(2);
                };
                height = Some(parsed);
            }
            "--workspace" => {
                let Some(value) = required_value(args, &mut index, "--workspace") else {
                    return Ok(2);
                };
                workspace_id = Some(value);
            }
            "--target-pane" => {
                let Some(value) = required_value(args, &mut index, "--target-pane") else {
                    return Ok(2);
                };
                target_pane_id = Some(value);
            }
            "--direction" => {
                let Some(value) = required_value(args, &mut index, "--direction") else {
                    return Ok(2);
                };
                let Some(parsed) = parse_split_direction(&value) else {
                    return Ok(2);
                };
                direction = Some(parsed);
            }
            "--cwd" => {
                let Some(value) = required_value(args, &mut index, "--cwd") else {
                    return Ok(2);
                };
                cwd = Some(value);
            }
            "--env" => {
                let Some(value) = required_value(args, &mut index, "--env") else {
                    return Ok(2);
                };
                let (key, value) = match super::parse_env_assignment(&value) {
                    Ok(pair) => pair,
                    Err(err) => {
                        eprintln!("{err}");
                        return Ok(2);
                    }
                };
                env.insert(key, value);
            }
            "--focus" => {
                focus = true;
                index += 1;
            }
            "--no-focus" => {
                focus = false;
                index += 1;
            }
            other => {
                eprintln!("unknown option: {other}");
                return Ok(2);
            }
        }
    }

    let Some(plugin_id) = plugin_id else {
        eprintln!("missing required --plugin");
        return Ok(2);
    };
    let Some(entrypoint) = entrypoint else {
        eprintln!("missing required --entrypoint");
        return Ok(2);
    };

    print_plugin_response(Method::PluginPaneOpen(PluginPaneOpenParams {
        plugin_id,
        entrypoint,
        placement,
        width,
        height,
        workspace_id,
        target_pane_id,
        direction,
        cwd,
        focus,
        env,
    }))
}

fn parse_popup_dimension(value: &str, flag: &str) -> Option<PopupSize> {
    match PopupSize::parse_cli(value) {
        Ok(value) => Some(value),
        Err(message) => {
            eprintln!("{flag} {message}");
            None
        }
    }
}

fn plugin_pane_focus(args: &[String]) -> std::io::Result<i32> {
    let Some(pane_id) = args.first() else {
        eprintln!("{}", crate::identity::usage("plugin pane focus <pane_id>"));
        return Ok(2);
    };
    if args.len() != 1 {
        eprintln!("{}", crate::identity::usage("plugin pane focus <pane_id>"));
        return Ok(2);
    }
    print_plugin_response(Method::PluginPaneFocus(PluginPaneFocusParams {
        pane_id: super::normalize_pane_id(pane_id),
    }))
}

fn plugin_pane_close(args: &[String]) -> std::io::Result<i32> {
    let Some(pane_id) = args.first() else {
        eprintln!("{}", crate::identity::usage("plugin pane close <pane_id>"));
        return Ok(2);
    };
    if args.len() != 1 {
        eprintln!("{}", crate::identity::usage("plugin pane close <pane_id>"));
        return Ok(2);
    }
    print_plugin_response(Method::PluginPaneClose(PluginPaneCloseParams {
        pane_id: super::normalize_pane_id(pane_id),
    }))
}

fn required_value(args: &[String], index: &mut usize, flag: &str) -> Option<String> {
    let Some(value) = args.get(*index + 1) else {
        eprintln!("missing value for {flag}");
        return None;
    };
    *index += 2;
    Some(value.clone())
}

fn parse_pane_placement(value: &str) -> Option<PluginPanePlacement> {
    match value {
        "overlay" => Some(PluginPanePlacement::Overlay),
        "popup" => Some(PluginPanePlacement::Popup),
        "split" => Some(PluginPanePlacement::Split),
        "tab" => Some(PluginPanePlacement::Tab),
        "zoomed" | "fullscreen" => Some(PluginPanePlacement::Zoomed),
        _ => {
            eprintln!("invalid pane placement: {value}");
            None
        }
    }
}

fn parse_split_direction(value: &str) -> Option<SplitDirection> {
    match value {
        "right" => Some(SplitDirection::Right),
        "down" => Some(SplitDirection::Down),
        _ => {
            eprintln!("invalid split direction: {value}");
            None
        }
    }
}

fn normalize_plugin_path_arg(value: &str) -> std::io::Result<String> {
    let path = crate::worktree::expand_tilde_path(value);
    let absolute = if path.is_absolute() {
        path
    } else {
        std::env::current_dir()?.join(path)
    };
    Ok(absolute.display().to_string())
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct GithubPluginSource {
    owner: String,
    repo: String,
    subdir: Option<String>,
}

impl GithubPluginSource {
    fn parse(value: &str) -> Result<Self, String> {
        if value.starts_with("http://")
            || value.starts_with("https://")
            || value.starts_with("git@")
            || value.contains(':')
        {
            return Err("expected <owner>/<repo>[/subdir...] shorthand".into());
        }
        let parts = value.split('/').collect::<Vec<_>>();
        if parts.len() < 2 {
            return Err("expected <owner>/<repo>[/subdir...]".into());
        }
        let owner = parts[0];
        let repo = parts[1];
        validate_github_segment("owner", owner)?;
        validate_github_segment("repo", repo)?;
        let subdir_parts = &parts[2..];
        for part in subdir_parts {
            validate_subdir_segment(part)?;
        }
        let subdir = if subdir_parts.is_empty() {
            None
        } else {
            Some(subdir_parts.join("/"))
        };
        Ok(Self {
            owner: owner.to_string(),
            repo: repo.to_string(),
            subdir,
        })
    }

    fn display(&self) -> String {
        match &self.subdir {
            Some(subdir) => format!("{}/{}/{}", self.owner, self.repo, subdir),
            None => format!("{}/{}", self.owner, self.repo),
        }
    }
}

fn validate_github_segment(label: &str, value: &str) -> Result<(), String> {
    if value.is_empty() {
        return Err(format!("GitHub {label} must not be empty"));
    }
    if value == "." || value == ".." {
        return Err(format!("GitHub {label} is invalid: {value}"));
    }
    if !value
        .chars()
        .all(|ch| ch.is_ascii_alphanumeric() || matches!(ch, '-' | '_' | '.'))
    {
        return Err(format!(
            "GitHub {label} contains invalid characters: {value}"
        ));
    }
    Ok(())
}

fn validate_subdir_segment(value: &str) -> Result<(), String> {
    if value.is_empty() || value == "." || value == ".." {
        return Err(format!("invalid plugin subdir segment: {value}"));
    }
    if value.contains('\\') || value.contains('\0') {
        return Err(format!("invalid plugin subdir segment: {value}"));
    }
    Ok(())
}

fn load_cli_plugin_manifest(path: &Path, enabled: bool) -> std::io::Result<InstalledPluginInfo> {
    crate::app::load_plugin_manifest(&path.display().to_string(), enabled)
        .map_err(|(_, message)| std::io::Error::other(message))
}

fn persist_plugin_offline(plugin: &InstalledPluginInfo) -> std::io::Result<()> {
    crate::plugin_paths::ensure_plugin_user_dirs(&plugin.plugin_id)?;
    crate::persist::plugin_registry::update(|plugins| {
        plugins.retain(|entry| entry.plugin_id != plugin.plugin_id);
        plugins.push(plugin.clone());
    })?;
    Ok(())
}

fn live_installed_plugin_info(plugin_id: &str) -> std::io::Result<Option<InstalledPluginInfo>> {
    let response = super::send_request(&Request {
        id: "cli:plugin".into(),
        method: Method::PluginList(PluginListParams {
            plugin_id: Some(plugin_id.to_string()),
        }),
    })?;
    if response.get("error").is_some() {
        return Err(std::io::Error::other(
            serde_json::to_string(&response).unwrap(),
        ));
    }
    plugin_info_from_list_response(response)
}

fn installed_plugin_by_github_source(
    source: &GithubPluginSource,
) -> std::io::Result<Option<InstalledPluginInfo>> {
    let plugins = match live_installed_plugins() {
        Ok(plugins) => plugins,
        Err(err) if is_connection_error(&err) => registry_plugins(),
        Err(err) => return Err(err),
    };
    Ok(plugin_by_github_source(plugins, source))
}

fn live_installed_plugins() -> std::io::Result<Vec<InstalledPluginInfo>> {
    let response = super::send_request(&Request {
        id: "cli:plugin".into(),
        method: Method::PluginList(PluginListParams { plugin_id: None }),
    })?;
    if response.get("error").is_some() {
        return Err(std::io::Error::other(
            serde_json::to_string(&response).unwrap(),
        ));
    }
    plugin_list_from_response(response)
}

fn registry_plugin_info(plugin_id: &str) -> Option<InstalledPluginInfo> {
    registry_plugins()
        .into_iter()
        .find(|plugin| plugin.plugin_id == plugin_id)
}

fn registry_plugins() -> Vec<InstalledPluginInfo> {
    crate::persist::plugin_registry::load()
}

fn plugin_info_from_list_response(
    response: serde_json::Value,
) -> std::io::Result<Option<InstalledPluginInfo>> {
    let mut plugins = plugin_list_from_response(response)?;
    Ok(plugins.pop())
}

fn plugin_list_from_response(
    response: serde_json::Value,
) -> std::io::Result<Vec<InstalledPluginInfo>> {
    let parsed: SuccessResponse =
        serde_json::from_value(response).map_err(std::io::Error::other)?;
    let ResponseResult::PluginList { mut plugins } = parsed.result else {
        return Err(std::io::Error::other("expected plugin_list response"));
    };
    plugins.sort_by(|a, b| a.plugin_id.cmp(&b.plugin_id));
    Ok(plugins)
}

fn plugin_by_github_source(
    plugins: impl IntoIterator<Item = InstalledPluginInfo>,
    source: &GithubPluginSource,
) -> Option<InstalledPluginInfo> {
    plugins
        .into_iter()
        .find(|plugin| plugin_matches_github_source(plugin, source))
}

fn plugin_matches_github_source(plugin: &InstalledPluginInfo, source: &GithubPluginSource) -> bool {
    plugin.source.kind == PluginSourceKind::Github
        && plugin.source.owner.as_deref() == Some(source.owner.as_str())
        && plugin.source.repo.as_deref() == Some(source.repo.as_str())
        && plugin.source.subdir.as_deref() == source.subdir.as_deref()
}

fn offline_plugin_link_response(params: &PluginLinkParams) -> std::io::Result<serde_json::Value> {
    let plugin = load_cli_plugin_manifest(Path::new(&params.path), params.enabled)?;
    persist_plugin_offline(&plugin)?;
    serde_json::to_value(SuccessResponse {
        id: "cli:plugin".into(),
        result: ResponseResult::PluginLinked { plugin },
    })
    .map_err(std::io::Error::other)
}

fn offline_plugin_list_response(params: &PluginListParams) -> std::io::Result<serde_json::Value> {
    let entries = crate::persist::plugin_registry::load();
    let mut plugins =
        crate::persist::plugin_registry::reload_manifests(entries, |path, enabled| {
            crate::app::load_plugin_manifest(path, enabled).map_err(|(_, msg)| msg)
        })
        .into_iter()
        .filter(|plugin| {
            params
                .plugin_id
                .as_deref()
                .is_none_or(|plugin_id| plugin.plugin_id == plugin_id)
        })
        .collect::<Vec<_>>();
    plugins.sort_by(|a, b| a.plugin_id.cmp(&b.plugin_id));
    serde_json::to_value(SuccessResponse {
        id: "cli:plugin".into(),
        result: ResponseResult::PluginList { plugins },
    })
    .map_err(std::io::Error::other)
}

fn print_plugin_list_human(response: &serde_json::Value) -> std::io::Result<i32> {
    if response.get("error").is_some() {
        return super::print_response(response);
    }
    let parsed: SuccessResponse =
        serde_json::from_value(response.clone()).map_err(std::io::Error::other)?;
    let ResponseResult::PluginList { plugins } = parsed.result else {
        return super::print_response(response);
    };
    if plugins.is_empty() {
        println!("No plugins installed.");
        return Ok(0);
    }
    println!(
        "{} plugin{} installed:",
        plugins.len(),
        if plugins.len() == 1 { "" } else { "s" }
    );
    for plugin in plugins {
        let enabled = if plugin.enabled {
            "enabled"
        } else {
            "disabled"
        };
        let warning = if plugin.warnings.is_empty() {
            String::new()
        } else {
            format!("; {} warning(s)", plugin.warnings.len())
        };
        println!(
            "- {} ({}) {} [{}{}]",
            plugin.plugin_id,
            plugin.name,
            enabled,
            source_display(&plugin),
            warning
        );
        println!(
            "  config: {}",
            crate::plugin_paths::plugin_config_dir(&plugin.plugin_id).display()
        );
        for warning in plugin.warnings {
            println!("  warning: {warning}");
        }
    }
    Ok(0)
}

fn source_display(plugin: &InstalledPluginInfo) -> String {
    match plugin.source.kind {
        PluginSourceKind::Github => {
            let owner = plugin.source.owner.as_deref().unwrap_or("unknown");
            let repo = plugin.source.repo.as_deref().unwrap_or("unknown");
            let subdir = plugin
                .source
                .subdir
                .as_deref()
                .map(|subdir| format!("/{subdir}"))
                .unwrap_or_default();
            let reference = plugin
                .source
                .requested_ref
                .as_deref()
                .or(plugin.source.resolved_commit.as_deref())
                .unwrap_or("unknown");
            format!("github:{owner}/{repo}{subdir}@{reference}")
        }
        PluginSourceKind::Local => format!("local:{}", plugin.plugin_root),
    }
}

fn remove_managed_plugin_files(plugin: &InstalledPluginInfo) -> std::io::Result<()> {
    if plugin.source.kind != PluginSourceKind::Github {
        return Ok(());
    }
    let Some(path) = plugin.source.managed_path.as_deref() else {
        return Ok(());
    };
    let path = PathBuf::from(path);
    if !path.exists() {
        return Ok(());
    }
    if !is_expected_managed_path(plugin, &path) {
        return Err(std::io::Error::other(format!(
            "refusing to delete unmanaged plugin path: {}",
            path.display()
        )));
    }
    std::fs::remove_dir_all(&path)
        .map_err(|err| plugin_checkout_lifecycle_error("remove", &path, err))
}

fn plugin_checkout_lifecycle_error(operation: &str, path: &Path, err: io::Error) -> io::Error {
    if cfg!(windows) && err.kind() == io::ErrorKind::PermissionDenied {
        return io::Error::new(
            err.kind(),
            format!(
                "failed to {operation} managed plugin checkout at {}; close any mrh-runtime plugin panes or plugin commands using that checkout, then retry: {err}",
                path.display()
            ),
        );
    }
    err
}

fn is_expected_managed_path(plugin: &InstalledPluginInfo, path: &Path) -> bool {
    let Ok(path) = path.canonicalize() else {
        return false;
    };
    let expected = crate::plugin_paths::managed_checkout_path(&plugin.plugin_id);
    let Ok(expected) = expected.canonicalize() else {
        return false;
    };
    path == expected
}

fn is_connection_error(err: &std::io::Error) -> bool {
    // A `server_not_running` marker is a connect failure for recovery purposes:
    // treating it as a connection error lets plugin commands fall back to the
    // offline registry. The marker carries (but does not print) a friendly
    // response, so recovering here prints nothing.
    super::server_not_running_was_reported(err)
        || matches!(
            err.kind(),
            std::io::ErrorKind::NotFound
                | std::io::ErrorKind::ConnectionRefused
                | std::io::ErrorKind::ConnectionAborted
                | std::io::ErrorKind::ConnectionReset
                | std::io::ErrorKind::BrokenPipe
        )
}

fn print_plugin_response(method: Method) -> std::io::Result<i32> {
    super::print_response(&super::send_request(&Request {
        id: "cli:plugin".into(),
        method,
    })?)
}

fn print_plugin_help() {
    eprintln!("{} plugin commands:", crate::identity::help_usage_name());
    eprintln!(
        "  {} plugin uninstall <plugin_id|owner/repo[/subdir...]>",
        crate::identity::help_usage_name()
    );
    eprintln!(
        "  {} plugin link <path> [--disabled]",
        crate::identity::help_usage_name()
    );
    eprintln!(
        "  {} plugin list [--plugin ID] [--json]",
        crate::identity::help_usage_name()
    );
    eprintln!(
        "  {} plugin config-dir <plugin_id>",
        crate::identity::help_usage_name()
    );
    eprintln!(
        "  {} plugin unlink <plugin_id>",
        crate::identity::help_usage_name()
    );
    eprintln!(
        "  {} plugin enable <plugin_id>",
        crate::identity::help_usage_name()
    );
    eprintln!(
        "  {} plugin disable <plugin_id>",
        crate::identity::help_usage_name()
    );
    eprintln!(
        "  {} plugin action <list|invoke>",
        crate::identity::help_usage_name()
    );
    eprintln!(
        "  {} plugin log list [--plugin ID] [--limit N]",
        crate::identity::help_usage_name()
    );
    eprintln!(
        "  {} plugin pane <open|focus|close>",
        crate::identity::help_usage_name()
    );
}

fn print_plugin_action_help() {
    eprintln!(
        "{} plugin action commands:",
        crate::identity::help_usage_name()
    );
    eprintln!(
        "  {} plugin action list [--plugin ID]",
        crate::identity::help_usage_name()
    );
    eprintln!(
        "  {} plugin action invoke <action_id> [--plugin ID]",
        crate::identity::help_usage_name()
    );
}

fn print_plugin_pane_help() {
    eprintln!(
        "{} plugin pane commands:",
        crate::identity::help_usage_name()
    );
    eprintln!("  {} plugin pane open --plugin ID --entrypoint ID [--placement overlay|popup|split|tab|zoomed] [--width SIZE] [--height SIZE] [--workspace ID] [--target-pane PANE] [--direction right|down] [--cwd PATH] [--env KEY=VALUE] [--focus|--no-focus]", crate::identity::help_usage_name());
    eprintln!(
        "  {} plugin pane focus <pane_id>",
        crate::identity::help_usage_name()
    );
    eprintln!(
        "  {} plugin pane close <pane_id>",
        crate::identity::help_usage_name()
    );
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::api::schema::PluginSourceInfo;
    use std::time::{SystemTime, UNIX_EPOCH};

    fn unique_plugin_id(label: &str) -> String {
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .map(|duration| duration.as_nanos())
            .unwrap_or(0);
        format!("test.{label}.{}.{nanos}", std::process::id())
    }

    fn github_plugin(
        id: &str,
        owner: &str,
        repo: &str,
        subdir: Option<&str>,
    ) -> InstalledPluginInfo {
        InstalledPluginInfo {
            plugin_id: id.to_string(),
            name: "Test Plugin".to_string(),
            version: "0.1.0".to_string(),
            min_herdr_version: crate::build_info::BASE_VERSION.to_string(),
            description: None,
            manifest_path: format!("/tmp/{id}/herdr-plugin.toml"),
            plugin_root: format!("/tmp/{id}"),
            enabled: true,
            platforms: None,
            build: vec![],
            startup: vec![],
            actions: vec![],
            events: vec![],
            panes: vec![],
            link_handlers: vec![],
            source: PluginSourceInfo {
                kind: PluginSourceKind::Github,
                owner: Some(owner.to_string()),
                repo: Some(repo.to_string()),
                subdir: subdir.map(str::to_string),
                requested_ref: None,
                resolved_commit: Some("abc123".to_string()),
                managed_path: Some(format!("/tmp/herdr/plugins/{id}")),
                installed_unix_ms: Some(42),
            },
            warnings: vec![],
        }
    }

    #[test]
    fn github_plugin_source_parses_root_repo() {
        let source = GithubPluginSource::parse("ogulcancelik/herdr-plugin-examples").unwrap();
        assert_eq!(source.owner, "ogulcancelik");
        assert_eq!(source.repo, "herdr-plugin-examples");
        assert_eq!(source.subdir, None);
    }

    #[test]
    fn github_plugin_source_parses_subdir() {
        let source =
            GithubPluginSource::parse("ogulcancelik/herdr-plugin-examples/worktree-bootstrap")
                .unwrap();
        assert_eq!(source.owner, "ogulcancelik");
        assert_eq!(source.repo, "herdr-plugin-examples");
        assert_eq!(source.subdir.as_deref(), Some("worktree-bootstrap"));
    }

    #[test]
    fn github_plugin_source_rejects_non_shorthand_sources() {
        for source in [
            "https://github.com/ogulcancelik/herdr-plugin-examples",
            "git@github.com:ogulcancelik/herdr-plugin-examples.git",
            "ogulcancelik",
            "ogulcancelik/herdr-plugin-examples/../bad",
            "ogulcancelik/herdr-plugin-examples//bad",
        ] {
            assert!(
                GithubPluginSource::parse(source).is_err(),
                "{source} should be rejected"
            );
        }
    }

    #[test]
    fn github_source_lookup_matches_installed_plugin_source() {
        let source =
            GithubPluginSource::parse("ogulcancelik/herdr-plugin-examples/agent-telegram-notify")
                .unwrap();
        let plugins = vec![
            github_plugin(
                "examples.github-link-preview",
                "ogulcancelik",
                "herdr-plugin-examples",
                Some("github-link-preview"),
            ),
            github_plugin(
                "examples.agent-telegram-notify",
                "ogulcancelik",
                "herdr-plugin-examples",
                Some("agent-telegram-notify"),
            ),
        ];

        let plugin = plugin_by_github_source(plugins, &source).unwrap();
        assert_eq!(plugin.plugin_id, "examples.agent-telegram-notify");
    }

    #[test]
    fn github_source_lookup_requires_exact_subdir() {
        let source = GithubPluginSource::parse("ogulcancelik/herdr-plugin-examples").unwrap();
        let plugins = vec![github_plugin(
            "examples.agent-telegram-notify",
            "ogulcancelik",
            "herdr-plugin-examples",
            Some("agent-telegram-notify"),
        )];

        assert!(plugin_by_github_source(plugins, &source).is_none());
    }

    #[test]
    fn github_source_lookup_ignores_local_plugins() {
        let source = GithubPluginSource::parse("ogulcancelik/herdr-plugin-examples").unwrap();
        let mut plugin = github_plugin(
            "examples.local",
            "ogulcancelik",
            "herdr-plugin-examples",
            None,
        );
        plugin.source = PluginSourceInfo::default();

        assert!(plugin_by_github_source([plugin], &source).is_none());
    }

    #[test]
    fn cli_user_dir_creation_seeds_legacy_config_before_printing_config_dir() {
        let plugin_id = unique_plugin_id("legacy-config");
        let config_dir = crate::plugin_paths::plugin_config_dir(&plugin_id);
        let state_dir = crate::plugin_paths::plugin_state_dir(&plugin_id);
        let legacy_dir = crate::config::config_dir().join("plugins").join(&plugin_id);
        let _ = std::fs::remove_dir_all(&config_dir);
        let _ = std::fs::remove_dir_all(&state_dir);
        let _ = std::fs::remove_dir_all(&legacy_dir);
        std::fs::create_dir_all(&legacy_dir).unwrap();
        std::fs::write(legacy_dir.join(".env"), "TOKEN=legacy\n").unwrap();

        assert_eq!(
            plugin_config_dir_command(std::slice::from_ref(&plugin_id)).unwrap(),
            0
        );

        assert_eq!(
            std::fs::read_to_string(config_dir.join(".env")).unwrap(),
            "TOKEN=legacy\n"
        );

        let _ = std::fs::remove_dir_all(config_dir);
        let _ = std::fs::remove_dir_all(state_dir);
        let _ = std::fs::remove_dir_all(legacy_dir);
    }
}
