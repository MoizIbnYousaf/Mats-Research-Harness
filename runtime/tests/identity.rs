//! The one identity of the shipped binary: its version line, its help banner
//! and its config directory.

use std::path::Path;
use std::process::Command;

fn run(args: &[&str], env: &[(&str, &str)]) -> std::process::Output {
    let mut command = Command::new(env!("CARGO_BIN_EXE_mrh-runtime"));
    command.args(args);
    command.env_remove("HERDR_SOCKET_PATH");
    command.env_remove("HERDR_CLIENT_SOCKET_PATH");
    command.env_remove("HERDR_ENV");
    command.env_remove("HERDR_CONFIG_PATH");
    command.env_remove("MRH_RUNTIME_CONFIG_PATH");
    for (key, value) in env {
        command.env(key, value);
    }
    command.output().expect("run mrh-runtime")
}

#[test]
fn version_is_one_exact_line() {
    let output = run(&["--version"], &[]);
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert_eq!(
        stdout,
        format!(
            "mrh-runtime {} (herdr 0.8.2 base, protocol 21)\n",
            env!("CARGO_PKG_VERSION")
        )
    );
}

#[test]
fn help_opens_with_the_banner_and_names_no_removed_surface() {
    let output = run(&["--help"], &[]);
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    assert_eq!(
        stdout.lines().next(),
        Some("mrh-runtime, the terminal wall for the harness study")
    );
    for banned in [
        "HI",
        "hi-runtime",
        "herdr.dev",
        "harness for harnesses",
        "director",
        "update",
        "--skill",
    ] {
        assert!(
            !stdout.contains(banned),
            "help mentions {banned:?}: {stdout}"
        );
    }
    assert!(stdout.contains("MRH_RUNTIME_CONFIG_PATH or HERDR_CONFIG_PATH"));
}

#[test]
fn config_dir_is_named_after_the_binary() {
    let base = std::env::temp_dir().join(format!(
        "mrh-runtime-identity-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map(|d| d.as_nanos())
            .unwrap_or(0)
    ));
    std::fs::create_dir_all(&base).unwrap();
    let output = run(&["--help"], &[("XDG_CONFIG_HOME", base.to_str().unwrap())]);
    assert!(output.status.success());
    let stdout = String::from_utf8_lossy(&output.stdout);
    let dir_name = if cfg!(debug_assertions) {
        "mrh-runtime-dev"
    } else {
        "mrh-runtime"
    };
    let expected = format!(
        "Config: {}",
        base.join(dir_name).join("config.toml").display()
    );
    assert!(
        stdout.lines().any(|line| line == expected),
        "help does not name the config dir {expected}: {stdout}"
    );
    assert!(
        !Path::new(&base).join("herdr").exists() && !Path::new(&base).join("hi-runtime").exists()
    );
    let _ = std::fs::remove_dir_all(&base);
}
