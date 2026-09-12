use super::harness::*;

#[test]
fn named_sessions_share_live_plugin_registry() {
    let base = unique_test_dir();
    let config_home = base.join("config");
    let runtime_dir = base.join("runtime");
    let first_dir = base.join("plugins").join("first");
    let second_dir = base.join("plugins").join("second");
    for (dir, id) in [
        (&first_dir, "example.first"),
        (&second_dir, "example.second"),
    ] {
        fs::create_dir_all(dir).unwrap();
        fs::write(
            dir.join("herdr-plugin.toml"),
            format!(
                "id = \"{id}\"\nname = \"{id}\"\nversion = \"0.1.0\"\nmin_herdr_version = \"0.6.10\"\n\n[[actions]]\nid = \"run\"\ntitle = \"Run\"\ncommand = [\"sh\", \"-c\", \"echo run\"]\n"
            ),
        )
        .unwrap();
    }

    let alpha = spawn_named_server(&config_home, &runtime_dir, "alpha");
    let beta = spawn_named_server(&config_home, &runtime_dir, "beta");
    wait_for_socket(
        &named_session_socket(&config_home, "alpha"),
        Duration::from_secs(5),
    );
    wait_for_socket(
        &named_session_socket(&config_home, "beta"),
        Duration::from_secs(5),
    );

    std::thread::scope(|scope| {
        let first = scope.spawn(|| {
            run_named_cli_json(
                &config_home,
                &runtime_dir,
                &[
                    "--session",
                    "alpha",
                    "plugin",
                    "link",
                    first_dir.to_str().unwrap(),
                ],
            )
        });
        let second = scope.spawn(|| {
            run_named_cli_json(
                &config_home,
                &runtime_dir,
                &[
                    "--session",
                    "beta",
                    "plugin",
                    "link",
                    second_dir.to_str().unwrap(),
                ],
            )
        });
        assert_eq!(
            first.join().unwrap()["result"]["plugin"]["plugin_id"],
            "example.first"
        );
        assert_eq!(
            second.join().unwrap()["result"]["plugin"]["plugin_id"],
            "example.second"
        );
    });

    let beta_list = run_named_cli_json(
        &config_home,
        &runtime_dir,
        &["--session", "beta", "plugin", "list", "--json"],
    );
    assert_eq!(beta_list["result"]["plugins"].as_array().unwrap().len(), 2);

    run_named_cli_json(
        &config_home,
        &runtime_dir,
        &["--session", "beta", "plugin", "disable", "example.first"],
    );
    let disabled = run_named_cli(
        &config_home,
        &runtime_dir,
        &[
            "--session",
            "alpha",
            "plugin",
            "action",
            "invoke",
            "run",
            "--plugin",
            "example.first",
        ],
    );
    assert_eq!(disabled.status.code(), Some(1));
    let disabled_output = format!(
        "{}{}",
        String::from_utf8_lossy(&disabled.stdout),
        String::from_utf8_lossy(&disabled.stderr)
    );
    assert!(disabled_output.contains("disabled"), "{disabled_output}");

    let _ = run_named_cli(&config_home, &runtime_dir, &["session", "stop", "alpha"]);
    let _ = run_named_cli(&config_home, &runtime_dir, &["session", "stop", "beta"]);
    drop(alpha);
    drop(beta);
    cleanup_test_base(&base);
}

#[test]
fn plugin_link_works_offline_and_is_global() {
    let base = unique_test_dir();
    let config_home = base.join("config");
    let runtime_dir = base.join("runtime");
    let state_home = base.join("state");
    let plugin_dir = base.join("plugins").join("offline");
    fs::create_dir_all(&plugin_dir).unwrap();
    fs::write(
        plugin_dir.join("herdr-plugin.toml"),
        r#"
id = "example.offline"
name = "Offline Plugin"
version = "0.1.0"
min_herdr_version = "0.6.10"
platforms = ["linux", "macos", "windows"]
"#,
    )
    .unwrap();

    let link_args = [
        "--session",
        "offline",
        "plugin",
        "link",
        plugin_dir.to_str().unwrap(),
        "--disabled",
    ];
    let linked = parse_cli_json_output(
        &link_args,
        run_named_cli_with_env(
            &config_home,
            &runtime_dir,
            &link_args,
            &[("XDG_STATE_HOME", &state_home)],
        ),
    );
    assert_eq!(linked["result"]["type"], "plugin_linked");
    assert_eq!(linked["result"]["plugin"]["plugin_id"], "example.offline");
    assert_eq!(linked["result"]["plugin"]["enabled"], false);
    assert_eq!(linked["result"]["plugin"]["source"]["kind"], "local");
    assert!(!named_session_socket(&config_home, "offline").exists());

    let listed = run_named_cli_json(
        &config_home,
        &runtime_dir,
        &["--session", "other", "plugin", "list", "--json"],
    );
    assert_eq!(listed["result"]["plugins"].as_array().unwrap().len(), 1);
    assert_eq!(
        listed["result"]["plugins"][0]["plugin_id"],
        "example.offline"
    );
    assert_eq!(listed["result"]["plugins"][0]["enabled"], false);

    cleanup_test_base(&base);
}

#[test]
fn plugin_link_list_unlink_cli_smoke_test() {
    let base = unique_test_dir();
    let config_home = base.join("config");
    let runtime_dir = base.join("runtime");
    let socket_path = runtime_dir.join("herdr.sock");
    let plugin_dir = base.join("plugins").join("layout");
    fs::create_dir_all(&plugin_dir).unwrap();
    fs::write(
        plugin_dir.join("herdr-plugin.toml"),
        r#"
id = "example.layout"
name = "Layout"
version = "0.1.0"
min_herdr_version = "0.6.10"
description = "Apply a preferred Herdr layout"

[[actions]]
id = "apply"
title = "Apply layout"
contexts = ["workspace"]
command = ["sh", "-c", "echo layout"]

[[events]]
on = "worktree.created"
command = ["sh", "-c", "echo worktree"]

[[panes]]
id = "board"
title = "Board"
placement = "tab"
command = ["sh", "-c", "sleep 5"]
"#,
    )
    .unwrap();

    let herdr = spawn_herdr(&config_home, &runtime_dir, &socket_path);
    wait_for_socket(&socket_path, Duration::from_secs(5));
    let workspace = run_cli_json(
        &socket_path,
        &[
            "workspace",
            "create",
            "--cwd",
            base.to_str().unwrap(),
            "--focus",
        ],
    );
    assert_eq!(workspace["result"]["type"], "workspace_created");

    let linked = run_cli_json_in_dir(&socket_path, &["plugin", "link", "plugins/layout"], &base);
    assert_eq!(linked["result"]["type"], "plugin_linked");
    assert_eq!(linked["result"]["plugin"]["plugin_id"], "example.layout");
    assert_eq!(linked["result"]["plugin"]["actions"][0]["id"], "apply");
    assert_eq!(
        linked["result"]["plugin"]["events"][0]["on"],
        "worktree.created"
    );
    assert_eq!(linked["result"]["plugin"]["panes"][0]["id"], "board");

    let listed_human = run_cli(&socket_path, &["plugin", "list"]);
    assert!(listed_human.status.success());
    assert!(String::from_utf8_lossy(&listed_human.stdout).contains("example.layout"));

    let listed = run_cli_json(&socket_path, &["plugin", "list", "--json"]);
    assert_eq!(listed["result"]["type"], "plugin_list");
    assert_eq!(
        listed["result"]["plugins"][0]["plugin_id"],
        "example.layout"
    );

    let invoked = run_cli_json(
        &socket_path,
        &[
            "plugin",
            "action",
            "invoke",
            "apply",
            "--plugin",
            "example.layout",
        ],
    );
    assert_eq!(invoked["result"]["type"], "plugin_action_invoked");
    assert_eq!(invoked["result"]["action"]["action_id"], "apply");

    let logs = run_cli_json(
        &socket_path,
        &[
            "plugin",
            "log",
            "list",
            "--plugin",
            "example.layout",
            "--limit",
            "5",
        ],
    );
    assert_eq!(logs["result"]["type"], "plugin_log_list");
    assert!(!logs["result"]["logs"].as_array().unwrap().is_empty());

    let pane = run_cli_json(
        &socket_path,
        &[
            "plugin",
            "pane",
            "open",
            "--plugin",
            "example.layout",
            "--entrypoint",
            "board",
            "--env",
            "HERDR_ROLE=board",
            "--no-focus",
        ],
    );
    assert_eq!(pane["result"]["type"], "plugin_pane_opened");
    assert_eq!(pane["result"]["plugin_pane"]["entrypoint"], "board");

    let missing_plugin_value = run_cli(&socket_path, &["plugin", "list", "--plugin"]);
    assert_eq!(missing_plugin_value.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&missing_plugin_value.stderr)
        .contains("missing value for --plugin"));

    let invalid_limit = run_cli(
        &socket_path,
        &["plugin", "log", "list", "--limit", "not-a-number"],
    );
    assert_eq!(invalid_limit.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&invalid_limit.stderr).contains("invalid --limit value"));

    let unlinked = run_cli_json(&socket_path, &["plugin", "unlink", "example.layout"]);
    assert_eq!(unlinked["result"]["type"], "plugin_unlinked");
    assert_eq!(unlinked["result"]["removed"], true);

    let listed = run_cli_json(&socket_path, &["plugin", "list", "--json"]);
    assert!(listed["result"]["plugins"].as_array().unwrap().is_empty());

    cleanup_spawned_herdr(herdr, base);
}
