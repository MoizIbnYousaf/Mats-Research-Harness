use crate::api::schema::IntegrationTarget;

pub(super) fn run_integration_command(args: &[String]) -> std::io::Result<i32> {
    let Some(subcommand) = args.first().map(|arg| arg.as_str()) else {
        print_integration_help();
        return Ok(2);
    };

    match subcommand {
        "install" => integration_install(&args[1..]),
        "uninstall" => integration_uninstall(&args[1..]),
        "status" => integration_status(&args[1..]),
        "help" | "--help" | "-h" => {
            print_integration_help();
            Ok(0)
        }
        _ => {
            print_integration_help();
            Ok(2)
        }
    }
}

fn integration_status(args: &[String]) -> std::io::Result<i32> {
    let outdated_only = match args {
        [] => false,
        [flag] if flag == "--outdated-only" => true,
        _ => {
            eprintln!(
                "{}",
                crate::identity::usage("integration status [--outdated-only]")
            );
            return Ok(2);
        }
    };

    if outdated_only {
        crate::integration::print_outdated_update_notice();
        return Ok(0);
    }

    for status in crate::integration::installed_integration_statuses() {
        let target = crate::integration::integration_target_label(status.target);
        let version = match status.installed_version {
            Some(version) => format!("v{version}"),
            None => "legacy".to_string(),
        };
        let state = match status.state {
            crate::integration::IntegrationStatusKind::NotInstalled => "not installed".to_string(),
            crate::integration::IntegrationStatusKind::Current => {
                format!("current ({version})")
            }
            crate::integration::IntegrationStatusKind::Outdated
                if status
                    .installed_version
                    .is_some_and(|installed| installed >= status.expected_version) =>
            {
                format!("needs repair ({version})")
            }
            crate::integration::IntegrationStatusKind::Outdated => {
                format!("outdated ({version} < v{})", status.expected_version)
            }
        };
        println!("{target}: {state} ({})", status.path.display());
    }

    Ok(0)
}

fn integration_install(args: &[String]) -> std::io::Result<i32> {
    let Some(target) = parse_integration_target(args, "install")? else {
        return Ok(2);
    };

    match crate::integration::install_target(target) {
        Ok(messages) => {
            print_integration_messages(messages);
            Ok(0)
        }
        Err(err) => {
            eprintln!("{err}");
            Ok(1)
        }
    }
}

fn integration_uninstall(args: &[String]) -> std::io::Result<i32> {
    let Some(target) = parse_integration_target(args, "uninstall")? else {
        return Ok(2);
    };

    match crate::integration::uninstall_target(target) {
        Ok(messages) => {
            print_integration_messages(messages);
            Ok(0)
        }
        Err(err) => {
            eprintln!("{err}");
            Ok(1)
        }
    }
}

fn print_integration_messages(messages: Vec<String>) {
    for message in messages {
        println!("{message}");
    }
}

fn parse_integration_target(
    args: &[String],
    action: &str,
) -> std::io::Result<Option<IntegrationTarget>> {
    let Some(target) = args.first().map(|arg| arg.as_str()) else {
        eprintln!(
            "{}",
            crate::identity::usage(&format!(
                "integration {action} <pi|omp|claude|codex|copilot|devin|droid|kimi|opencode|kilo|hermes|qodercli|qwen|cursor|mastracode|grok>"
            ))
        );
        return Ok(None);
    };
    if args.len() != 1 {
        eprintln!(
            "{}",
            crate::identity::usage(&format!(
                "integration {action} <pi|omp|claude|codex|copilot|devin|droid|kimi|opencode|kilo|hermes|qodercli|qwen|cursor|mastracode|grok>"
            ))
        );
        return Ok(None);
    }

    let parsed = match target {
        "pi" => IntegrationTarget::Pi,
        "omp" => IntegrationTarget::Omp,
        "claude" => IntegrationTarget::Claude,
        "codex" => IntegrationTarget::Codex,
        "copilot" => IntegrationTarget::Copilot,
        "devin" => IntegrationTarget::Devin,
        "droid" => IntegrationTarget::Droid,
        "kimi" => IntegrationTarget::Kimi,
        "opencode" => IntegrationTarget::Opencode,
        "kilo" => IntegrationTarget::Kilo,
        "hermes" => IntegrationTarget::Hermes,
        "qodercli" => IntegrationTarget::Qodercli,
        "qwen" => IntegrationTarget::Qwen,
        "cursor" => IntegrationTarget::Cursor,
        "mastracode" => IntegrationTarget::Mastracode,
        "antigravity-cli" | "antigravity_cli" => IntegrationTarget::AntigravityCli,
        "grok" => IntegrationTarget::Grok,
        _ => {
            eprintln!("unknown integration target: {target}");
            eprintln!(
                "currently supported: pi, omp, claude, codex, copilot, devin, droid, kimi, opencode, kilo, hermes, qodercli, qwen, cursor, mastracode, antigravity-cli, grok"
            );
            return Ok(None);
        }
    };

    Ok(Some(parsed))
}

fn print_integration_help() {
    let bin = crate::identity::help_usage_name();
    eprintln!("{bin} integration commands:");
    eprintln!("  {bin} integration install pi");
    eprintln!("  {bin} integration install omp");
    eprintln!("  {bin} integration install claude");
    eprintln!("  {bin} integration install codex");
    eprintln!("  {bin} integration install copilot");
    eprintln!("  {bin} integration install devin");
    eprintln!("  {bin} integration install droid");
    eprintln!("  {bin} integration install kimi");
    eprintln!("  {bin} integration install opencode");
    eprintln!("  {bin} integration install kilo");
    eprintln!("  {bin} integration install hermes");
    eprintln!("  {bin} integration install qodercli");
    eprintln!("  {bin} integration install qwen");
    eprintln!("  {bin} integration install cursor");
    eprintln!("  {bin} integration install mastracode");
    eprintln!("  {bin} integration install antigravity-cli");
    eprintln!("  {bin} integration install grok");
    eprintln!("  {bin} integration uninstall pi");
    eprintln!("  {bin} integration uninstall omp");
    eprintln!("  {bin} integration uninstall claude");
    eprintln!("  {bin} integration uninstall codex");
    eprintln!("  {bin} integration uninstall copilot");
    eprintln!("  {bin} integration uninstall devin");
    eprintln!("  {bin} integration uninstall droid");
    eprintln!("  {bin} integration uninstall kimi");
    eprintln!("  {bin} integration uninstall opencode");
    eprintln!("  {bin} integration uninstall kilo");
    eprintln!("  {bin} integration uninstall hermes");
    eprintln!("  {bin} integration uninstall qodercli");
    eprintln!("  {bin} integration uninstall qwen");
    eprintln!("  {bin} integration uninstall cursor");
    eprintln!("  {bin} integration uninstall mastracode");
    eprintln!("  {bin} integration uninstall antigravity-cli");
    eprintln!("  {bin} integration uninstall grok");
    eprintln!("  {bin} integration status [--outdated-only]");
}
