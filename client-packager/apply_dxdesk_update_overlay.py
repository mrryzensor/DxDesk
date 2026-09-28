#!/usr/bin/env python3
"""Reapply DxDesk's installation and GitHub update overlay."""
from __future__ import annotations
import re
from pathlib import Path
DXDESK_INNO_APP_ID = "{E380B41C-8D57-48BC-96E6-8E383845496B}"
def replace_once(path: Path, old: str, new: str) -> None:
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8")
    if old in content:
        path.write_text(content.replace(old, new, 1), encoding="utf-8", newline="")
def replace_regex(path: Path, pattern: str, replacement: str, flags: int = 0) -> None:
    if not path.exists():
        return
    content = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, replacement, content, count=1, flags=flags)
    if count:
        path.write_text(updated, encoding="utf-8", newline="")
COMMON_HELPER = r'''const DXDESK_GITHUB_RELEASES_API: &str =
    "https://api.github.com/repos/mrryzensor/DxDesk/releases?per_page=20";
fn dxdesk_update_asset_name() -> Option<&'static str> {
    #[cfg(target_os = "windows")]
    return Some("DxDesk-Windows-x64.exe");
    #[cfg(target_os = "linux")]
    return Some("DxDesk-Linux-x64.AppImage");
    #[cfg(target_os = "macos")]
    return Some(if std::env::consts::ARCH == "aarch64" { "DxDesk-macOS-AppleSilicon.dmg" } else { "DxDesk-macOS-Intel.dmg" });
    #[cfg(target_os = "android")]
    return Some("DxDesk-Android-Universal.apk");
    #[cfg(target_os = "ios")]
    return None;
    #[allow(unreachable_code)]
    None
}
fn dxdesk_release_is_newer(tag: &str) -> bool {
    if let Some(current_tag) = option_env!("DXDESK_BUILD_TAG").filter(|tag| !tag.is_empty()) {
        let normalize = |value: &str| value.strip_prefix("source-").unwrap_or(value);
        return normalize(tag) != normalize(current_tag);
    }
    get_version_number(tag) > get_version_number(crate::VERSION)
}
async fn do_check_dxdesk_software_update() -> hbb_common::ResultType<()> {
    let Some(asset_name) = dxdesk_update_asset_name() else {
        *SOFTWARE_UPDATE_URL.lock().unwrap() = String::new();
        *SOFTWARE_UPDATE_DOWNLOAD_URL.lock().unwrap() = String::new();
        return Ok(());
    };
    let proxy_conf = Config::get_socks();
    let tls_url = get_url_for_tls(DXDESK_GITHUB_RELEASES_API, &proxy_conf);
    let tls_type = get_cached_tls_type(tls_url);
    let is_tls_not_cached = tls_type.is_none();
    let tls_type = tls_type.unwrap_or(TlsType::Rustls);
    let client = create_http_client_async(tls_type, false);
    let response = match client.get(DXDESK_GITHUB_RELEASES_API).header("User-Agent", "DxDesk").send().await {
        Ok(resp) => { upsert_tls_cache(tls_url, tls_type, false); resp }
        Err(err) if is_tls_not_cached && err.is_request() => {
            let tls_type = TlsType::NativeTls;
            let client = create_http_client_async(tls_type, false);
            let resp = client.get(DXDESK_GITHUB_RELEASES_API).header("User-Agent", "DxDesk").send().await?;
            upsert_tls_cache(tls_url, tls_type, false);
            resp
        }
        Err(err) => return Err(err.into()),
    };
    if !response.status().is_success() { bail!("DxDesk update service returned HTTP {}", response.status()); }
    let releases: Vec<Value> = serde_json::from_slice(&response.bytes().await?)?;
    let mut release_page_url = String::new();
    let mut download_url = String::new();
    for release in releases {
        if release.get("draft").and_then(Value::as_bool).unwrap_or(true) || release.get("prerelease").and_then(Value::as_bool).unwrap_or(false) { continue; }
        let Some(tag) = release.get("tag_name").and_then(Value::as_str) else { continue; };
        let Some(asset_url) = release.get("assets").and_then(Value::as_array).and_then(|assets| assets.iter().find_map(|asset| {
            (asset.get("name").and_then(Value::as_str) == Some(asset_name)).then(|| asset.get("browser_download_url").and_then(Value::as_str)).flatten()
        })) else { continue; };
        if dxdesk_release_is_newer(tag) {
            release_page_url = release.get("html_url").and_then(Value::as_str).unwrap_or_default().to_owned();
            download_url = asset_url.to_owned();
        }
        break;
    }
    if !release_page_url.is_empty() && !download_url.is_empty() {
        #[cfg(feature = "flutter")]
        {
            let mut m = HashMap::new();
            m.insert("name", "check_software_update_finish");
            m.insert("url", release_page_url.as_str());
            if let Ok(data) = serde_json::to_string(&m) { let _ = crate::flutter::push_global_event(crate::flutter::APP_TYPE_MAIN, data); }
        }
        *SOFTWARE_UPDATE_URL.lock().unwrap() = release_page_url;
        *SOFTWARE_UPDATE_DOWNLOAD_URL.lock().unwrap() = download_url;
    } else {
        *SOFTWARE_UPDATE_URL.lock().unwrap() = String::new();
        *SOFTWARE_UPDATE_DOWNLOAD_URL.lock().unwrap() = String::new();
    }
    Ok(())
}
'''
UPDATER_BLOCK = r'''        let (download_url, version) = if crate::is_custom_client() {
            let download_url = crate::common::SOFTWARE_UPDATE_DOWNLOAD_URL.lock().unwrap().clone();
            if download_url.is_empty() { log::debug!("No DxDesk update asset available."); return Ok(()); }
            (download_url, crate::ui_interface::get_new_version())
        } else {
            let download_root = update_url.replace("tag", "download");
            let version = download_root.split('/').last().unwrap_or_default();
            #[cfg(target_os = "windows")]
            let download_url = if cfg!(feature = "flutter") {
                let Some(arch) = crate::platform::windows::release_arch_suffix() else { bail!("Unsupported Windows release architecture: {}", std::env::consts::ARCH); };
                format!("{}/rustdesk-{}-{}.{}", download_root, version, arch, if update_msi { "msi" } else { "exe" })
            } else { format!("{}/rustdesk-{}-x86-sciter.exe", download_root, version) };
            #[cfg(not(target_os = "windows"))]
            let download_url = format!("{}/rustdesk-{}-x86_64.dmg", download_root, version);
            (download_url, version.to_owned())
        };
        log::debug!("New version available: {}", &version);'''
def apply_update_overlay(client_dir: Path, app_name: str = "DxDesk") -> None:
    common_rs = client_dir / "src" / "common.rs"
    if common_rs.exists():
        content = common_rs.read_text(encoding="utf-8")
        if "SOFTWARE_UPDATE_DOWNLOAD_URL" not in content:
            content = content.replace("    pub static ref SOFTWARE_UPDATE_URL: Arc<Mutex<String>> = Default::default();", "    pub static ref SOFTWARE_UPDATE_URL: Arc<Mutex<String>> = Default::default();\n    pub static ref SOFTWARE_UPDATE_DOWNLOAD_URL: Arc<Mutex<String>> = Default::default();", 1)
        content = re.sub(r"pub fn check_software_update\(\) \{\n\s*if is_custom_client\(\) \{\n\s*return;\n\s*\}\n", "pub fn check_software_update() {\n", content, count=1)
        if "DXDESK_GITHUB_RELEASES_API" not in content:
            content = content.replace("// No need to check `danger_accept_invalid_cert` for now.", COMMON_HELPER + "// No need to check `danger_accept_invalid_cert` for now.", 1)
        if "return do_check_dxdesk_software_update().await;" not in content:
            content = content.replace("pub async fn do_check_software_update() -> hbb_common::ResultType<()> {\n", "pub async fn do_check_software_update() -> hbb_common::ResultType<()> {\n    if is_custom_client() {\n        return do_check_dxdesk_software_update().await;\n    }\n", 1)
        common_rs.write_text(content, encoding="utf-8", newline="")
    updater_rs = client_dir / "src" / "updater.rs"
    if updater_rs.exists():
        content = updater_rs.read_text(encoding="utf-8")
        content = content.replace(
            "    let update_msi = crate::platform::is_msi_installed()? && !crate::is_custom_client();",
            "    let update_msi = !crate::is_custom_client() && crate::platform::is_msi_installed()?;",
            1,
        )
        if "SOFTWARE_UPDATE_DOWNLOAD_URL" not in content:
            content = re.sub(r"        let download_url = update_url\.replace\(\"tag\", \"download\"\);.*?        log::debug!\(\"New version available: \{\}\", &version\);", UPDATER_BLOCK, content, count=1, flags=re.DOTALL)
        if "owner == \"mrryzensor\"" not in content:
            content = content.replace('    if owner != "rustdesk"\n        || repo != "rustdesk"\n        || releases != "releases"', '    let is_trusted_repository =\n        (owner == "rustdesk" && repo == "rustdesk")\n            || (owner == "mrryzensor" && repo == "DxDesk");\n    if !is_trusted_repository\n        || releases != "releases"', 1)
        updater_rs.write_text(content, encoding="utf-8", newline="")
    windows_rs = client_dir / "src" / "platform" / "windows.rs"
    replace_regex(windows_rs, r'(?m)^const IS1: &str = "[^"]+";', f'const IS1: &str = "{DXDESK_INNO_APP_ID}_is1";')
    replace_once(
        windows_rs,
        '    let exe = format!("{}\\\\{}.exe", path, crate::get_app_name());\n    (subkey, path, start_menu, exe)',
        '''    let exe = format!("{}\\\\{}.exe", path, crate::get_app_name());
    // Older branded installers used rustdesk.exe. Keep them detectable while
    // new packages consistently use DxDesk.exe.
    let exe = if !std::path::Path::new(&exe).exists() && crate::is_custom_client() {
        let legacy_exe = format!("{}\\\\rustdesk.exe", path);
        if std::path::Path::new(&legacy_exe).exists() {
            legacy_exe
        } else {
            exe
        }
    } else {
        exe
    };
    (subkey, path, start_menu, exe)''',
    )
    replace_once(
        client_dir / "src" / "ui_interface.rs",
        "        return crate::BUILD_DATE.cmp(&b).is_gt();",
        "        return !b.is_empty() && crate::BUILD_DATE.cmp(&b).is_gt();",
    )
    replace_once(
        windows_rs,
        '''    format!("{}\\\\{}", pf, crate::get_app_name())''',
        '''    let preferred = format!("{}\\\\{}", pf, crate::get_app_name());
    if std::path::Path::new(&preferred).exists() {
        return preferred;
    }
    if let Ok(pf32) = std::env::var("ProgramFiles(x86)") {
        let legacy = format!("{}\\\\{}", pf32, crate::get_app_name());
        if std::path::Path::new(&legacy).exists() {
            return legacy;
        }
    }
    preferred''',
    )
    iss = Path(__file__).resolve().parent / "inno_setup_dxdesk.iss"
    replace_once(iss, "PrivilegesRequired=lowest", "PrivilegesRequired=admin")
    common_dart = client_dir / "flutter" / "lib" / "common.dart"
    replace_regex(
        common_dart,
        r"(?s)void checkUpdate\(\) \{.*?\n\}",
        '''void checkUpdate() {
  if (!isWeb) {
    platformFFI.registerEventHandler(
        kCheckSoftwareUpdateFinish, kCheckSoftwareUpdateFinish,
        (Map<String, dynamic> evt) async {
      if (evt['url'] is String) {
        stateGlobal.updateUrl.value = evt['url'];
      }
    });
    Timer(const Duration(seconds: 1), () async {
      bind.mainGetSoftwareUpdateUrl();
    });
  }
}''',
    )
    home_page = client_dir / "flutter" / "lib" / "desktop" / "pages" / "desktop_home_page.dart"
    replace_once(home_page, """    if (!bind.isCustomClient() &&
        updateUrl.isNotEmpty &&
        !isCardClosed &&
        bind.mainUriPrefixSync().contains('rustdesk')) {""", """    if (updateUrl.isNotEmpty && !isCardClosed &&
        (bind.isCustomClient() ||
            bind.mainUriPrefixSync().contains('rustdesk'))) {""")
    replace_once(home_page, "final Uri url = Uri.parse('https://rustdesk.com/download');", "final Uri url = Uri.parse(bind.isCustomClient()\n            ? updateUrl\n            : 'https://rustdesk.com/download');")
    replace_once(home_page, """          link: isToUpdate
              ? 'https://github.com/rustdesk/rustdesk/releases/tag/${bind.mainGetNewVersion()}'
              : null);""", """          link: isToUpdate ? updateUrl : null);""")
    connection_page = client_dir / "flutter" / "lib" / "mobile" / "pages" / "connection_page.dart"
    replace_once(connection_page, "if (!bind.isCustomClient() && !isIOS)", "if (!isIOS)")
    replace_once(connection_page, "final url = 'https://rustdesk.com/download';", "final url = bind.isCustomClient()\n                  ? updateUrl\n                  : 'https://rustdesk.com/download';")
    update_progress = client_dir / "flutter" / "lib" / "desktop" / "widgets" / "update_progress.dart"
    replace_once(update_progress, """  String downloadUrl = releasePageUrl.replaceAll('tag', 'download');
  String version = downloadUrl.substring(downloadUrl.lastIndexOf('/') + 1);
  final String downloadFile =
      bind.mainGetCommonSync(key: 'download-file-$version');""", """  String downloadUrl;
  String downloadFile;
  if (bind.isCustomClient()) {
    downloadUrl = bind.mainGetCommonSync(key: 'download-file-custom');
    downloadFile = downloadUrl;
  } else {
    downloadUrl = releasePageUrl.replaceAll('tag', 'download');
    String version = downloadUrl.substring(downloadUrl.lastIndexOf('/') + 1);
    downloadFile = bind.mainGetCommonSync(key: 'download-file-$version');
  }""")
    replace_once(update_progress, """  downloadUrl = '$downloadUrl/$downloadFile';

  SimpleWrapper downloadId""", """  if (!bind.isCustomClient()) {
    downloadUrl = '$downloadUrl/$downloadFile';
  }

  SimpleWrapper downloadId""")
    ffi_rs = client_dir / "src" / "flutter_ffi.rs"
    replace_once(ffi_rs, '        } else if key.starts_with("download-file-") {\n            let _version = key.replace("download-file-", "");', '        } else if key.starts_with("download-file-") {\n            if key == "download-file-custom" {\n                return crate::common::SOFTWARE_UPDATE_DOWNLOAD_URL\n                    .lock()\n                    .unwrap()\n                    .clone();\n            }\n            let _version = key.replace("download-file-", "");')
