//! The one identity of this binary: its name, title, version line, config
//! directory and default theme. Every user-facing surface reads from here.

pub const BINARY: &str = "mrh-runtime";
pub const TITLE: &str = "the terminal wall for the harness study";
pub const HELP_BANNER: &str = "mrh-runtime, the terminal wall for the harness study";
/// The herdr release this kernel was cut from. Attribution lives in NOTICE.md
/// at the repository root and in runtime/README.md.
pub const HERDR_BASE_VERSION: &str = "0.8.2";
pub const CONFIG_DIR: &str = "mrh-runtime";
pub const CONFIG_DIR_DEV: &str = "mrh-runtime-dev";
pub const DEFAULT_THEME: &str = "tokyo-night";
pub const DEFAULT_THEME_LIGHT: &str = "tokyo-night-day";

/// The single `--version` line.
pub fn version_line(version: &str) -> String {
    format!(
        "{BINARY} {version} (herdr {HERDR_BASE_VERSION} base, protocol {})",
        crate::protocol::PROTOCOL_VERSION
    )
}

/// First line of `--help` and the clap `about` text.
pub fn help_banner() -> &'static str {
    HELP_BANNER
}

/// Directory name under XDG config and state roots.
pub fn persist_dir_name() -> &'static str {
    if cfg!(debug_assertions) {
        CONFIG_DIR_DEV
    } else {
        CONFIG_DIR
    }
}

/// Command name printed in usage lines and help output.
pub fn help_usage_name() -> &'static str {
    BINARY
}

/// Syntax-error usage line.
pub fn usage(rest: &str) -> String {
    format!("usage: {BINARY} {rest}")
}

/// Multi-line usage. Later lines also start with the command name.
pub fn usage_stack(lines: &[&str]) -> String {
    let mut out = String::new();
    for (index, line) in lines.iter().enumerate() {
        if index == 0 {
            out.push_str(&format!("usage: {BINARY} {line}"));
        } else {
            out.push_str(&format!("\n       {BINARY} {line}"));
        }
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn version_line_names_the_binary_and_the_herdr_base() {
        assert_eq!(
            version_line("0.1.0"),
            "mrh-runtime 0.1.0 (herdr 0.8.2 base, protocol 21)"
        );
        assert_eq!(
            version_line(env!("CARGO_PKG_VERSION")),
            format!(
                "mrh-runtime {} (herdr 0.8.2 base, protocol {})",
                env!("CARGO_PKG_VERSION"),
                crate::protocol::PROTOCOL_VERSION
            )
        );
    }

    #[test]
    fn help_banner_is_the_contract_line() {
        assert_eq!(
            help_banner(),
            "mrh-runtime, the terminal wall for the harness study"
        );
        assert_eq!(help_banner(), format!("{BINARY}, {TITLE}"));
    }

    #[test]
    fn persist_dir_is_mrh_runtime() {
        let dir = persist_dir_name();
        assert_eq!(dir, crate::config::app_dir_name());
        assert_eq!(
            dir,
            if cfg!(debug_assertions) {
                "mrh-runtime-dev"
            } else {
                "mrh-runtime"
            }
        );
    }

    #[test]
    fn usage_lines_start_with_the_binary() {
        assert_eq!(help_usage_name(), "mrh-runtime");
        assert_eq!(
            usage("pane create --crew"),
            "usage: mrh-runtime pane create --crew"
        );
        assert_eq!(
            usage_stack(&[
                "pane swap --direction left",
                "pane swap --source-pane ID --target-pane ID",
            ]),
            "usage: mrh-runtime pane swap --direction left\n       mrh-runtime pane swap --source-pane ID --target-pane ID"
        );
    }
}
