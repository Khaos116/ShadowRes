"""
ShadowRes APK publish helper.

Usage:
  python publish_apk.py <apk_path> [--host]

Examples:
  # Publish a plugin APK (auto-detect plugin id from filename)
  python publish_apk.py E:/Work/LiveWos2027/APK/plugin/live2026-plugin-login_Debug_1.0.0_20260720_025420.apk

  # Publish the host APK
  python publish_apk.py E:/Work/LiveWos2027/APK/app_Debug_1.0.0_20260720_013252.apk --host
"""
import json
import hashlib
import os
import subprocess
import base64
import shutil
import sys
import re

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
APK_DIR = os.path.join(REPO_DIR, "apk")
MANIFEST_PATH = os.path.join(REPO_DIR, "json", "plugin_manifest.json")
PRIVATE_KEY_PATH = "E:/work/LiveWos2027/jks/plugin_signing_private.pem"
GITHUB_BASE = "https://raw.githubusercontent.com/Khaos116/ShadowRes/main/apk"


def sha256_of_file(path):
    with open(path, 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest(), open(path, 'rb').read()


def sha256_and_sign(apk_path):
    with open(apk_path, 'rb') as f:
        apk_bytes = f.read()
    hash_hex = hashlib.sha256(apk_bytes).hexdigest()
    hash_bytes = bytes.fromhex(hash_hex)

    tmp_hash = os.path.join(REPO_DIR, "tmp_hash.bin")
    with open(tmp_hash, 'wb') as f:
        f.write(hash_bytes)

    result = subprocess.run(
        ['openssl', 'pkeyutl', '-sign', '-in', tmp_hash,
         '-inkey', PRIVATE_KEY_PATH, '-pkeyopt', 'digest:sha256'],
        capture_output=True, check=True
    )
    os.remove(tmp_hash)
    signature = base64.b64encode(result.stdout).decode('utf-8')
    return hash_hex, signature


def detect_plugin_id(apk_name):
    """Detect plugin id from APK filename.
    e.g. live2026-plugin-login_Debug_1.0.0_xxx.apk -> login
         lib-plugin-net_Debug_1.0.0_xxx.apk -> net
    """
    m = re.search(r'(?:live2026-plugin-|lib-plugin-)([a-zA-Z]+)_', apk_name)
    if m:
        return m.group(1)
    return None


def remove_old_apks(prefix):
    """Remove APKs in the apk/ dir that share the same prefix, return list of removed names."""
    removed = []
    for f in os.listdir(APK_DIR):
        if f.startswith(prefix) and f.endswith('.apk'):
            os.remove(os.path.join(APK_DIR, f))
            removed.append(f)
    return removed


def git_rm(files):
    for f in files:
        rel = os.path.relpath(os.path.join(APK_DIR, f), REPO_DIR).replace('\\', '/')
        subprocess.run(['git', 'rm', '-f', rel], cwd=REPO_DIR, check=False, capture_output=True)


def publish_plugin(apk_path):
    apk_name = os.path.basename(apk_path)
    plugin_id = detect_plugin_id(apk_name)
    if not plugin_id:
        print(f"ERROR: Cannot detect plugin id from {apk_name}")
        sys.exit(1)

    print(f"Plugin id detected: {plugin_id}")

    # Detect prefix to cleanup old apks
    if 'live2026-plugin' in apk_name:
        prefix = f"live2026-plugin-{plugin_id}_"
    else:
        prefix = f"lib-plugin-{plugin_id}_"

    # Remove old APKs from disk
    old_apks = remove_old_apks(prefix)
    if old_apks:
        git_rm(old_apks)
        print(f"Removed old APKs: {old_apks}")

    # Copy new APK
    dest = os.path.join(APK_DIR, apk_name)
    shutil.copy2(apk_path, dest)
    print(f"Copied {apk_name} to apk/")

    # Sign
    hash_hex, signature = sha256_and_sign(dest)
    print(f"SHA256: {hash_hex}")

    # Update manifest
    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    entry = next((p for p in manifest['plugins'] if p['id'] == plugin_id), None)
    url = f"{GITHUB_BASE}/{apk_name}"
    if entry:
        entry['url'] = url
        entry['sha256'] = hash_hex
        entry['signature'] = signature
        print(f"Updated existing plugin entry: {plugin_id}")
    else:
        manifest['plugins'].append({
            "id": plugin_id,
            "version": "1.0.0",
            "url": url,
            "sha256": hash_hex,
            "signature": signature,
            "minHostVersion": 1
        })
        print(f"Added new plugin entry: {plugin_id}")

    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    # Git add and commit
    subprocess.run(['git', 'add', f'apk/{apk_name}', 'json/plugin_manifest.json'],
                   cwd=REPO_DIR, check=True)
    subprocess.run(['git', 'commit', '-m', f'publish plugin: {plugin_id} ({apk_name})'],
                   cwd=REPO_DIR, check=True)
    subprocess.run(['git', 'push', 'origin', 'main'], cwd=REPO_DIR, check=True)
    print(f"Done! Plugin {plugin_id} published.")


def publish_host(apk_path):
    apk_name = os.path.basename(apk_path)

    # Remove old host APKs (prefix = app_)
    old_apks = remove_old_apks("app_")
    if old_apks:
        git_rm(old_apks)
        print(f"Removed old host APKs: {old_apks}")

    # Copy new APK
    dest = os.path.join(APK_DIR, apk_name)
    shutil.copy2(apk_path, dest)
    print(f"Copied {apk_name} to apk/")

    # Git add and commit (host APK doesn't need signing)
    subprocess.run(['git', 'add', f'apk/{apk_name}'],
                   cwd=REPO_DIR, check=True)
    subprocess.run(['git', 'commit', '-m', f'publish host: {apk_name}'],
                   cwd=REPO_DIR, check=True)
    subprocess.run(['git', 'push', 'origin', 'main'], cwd=REPO_DIR, check=True)
    print(f"Done! Host APK published: {apk_name}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    apk_path = sys.argv[1].replace('\\', '/')
    is_host = '--host' in sys.argv

    if not os.path.exists(apk_path):
        print(f"ERROR: APK not found: {apk_path}")
        sys.exit(1)

    if is_host:
        publish_host(apk_path)
    else:
        publish_plugin(apk_path)
