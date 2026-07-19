import json
import hashlib
import os
import subprocess
import base64

def sign_apk(apk_path, private_key_path):
    # Calculate SHA256 of APK
    with open(apk_path, 'rb') as f:
        apk_hash_bytes = hashlib.sha256(f.read()).digest()
    
    apk_hash_hex = apk_hash_bytes.hex()
    
    # Save hash bytes to temp file
    temp_hash_path = "temp_hash.bin"
    with open(temp_hash_path, 'wb') as f:
        f.write(apk_hash_bytes)
        
    # Sign using openssl
    result = subprocess.run([
        'openssl', 'pkeyutl', '-sign', 
        '-in', temp_hash_path, 
        '-inkey', private_key_path, 
        '-pkeyopt', 'digest:sha256'
    ], capture_output=True, check=True)
    
    signature_bytes = result.stdout
    signature_b64 = base64.b64encode(signature_bytes).decode('utf-8')
    
    os.remove(temp_hash_path)
    
    return apk_hash_hex, signature_b64

apk_file = "live2026-plugin-login_Debug_1.0.0_20260720_025114.apk"
apk_path = os.path.join("E:/work/ShadowRes/apk", apk_file)
private_key_path = "E:/work/LiveWos2027/jks/plugin_signing_private.pem"
manifest_path = "E:/work/ShadowRes/json/plugin_manifest.json"

hash_hex, signature_b64 = sign_apk(apk_path, private_key_path)

with open(manifest_path, 'r', encoding='utf-8') as f:
    manifest = json.load(f)

# Add or update login plugin
login_plugin = next((p for p in manifest['plugins'] if p['id'] == 'login'), None)
if login_plugin:
    login_plugin['url'] = f"https://raw.githubusercontent.com/Khaos116/ShadowRes/main/apk/{apk_file}"
    login_plugin['sha256'] = hash_hex
    login_plugin['signature'] = signature_b64
else:
    manifest['plugins'].append({
        "id": "login",
        "version": "1.0.0",
        "url": f"https://raw.githubusercontent.com/Khaos116/ShadowRes/main/apk/{apk_file}",
        "sha256": hash_hex,
        "signature": signature_b64,
        "minHostVersion": 1
    })

with open(manifest_path, 'w', encoding='utf-8') as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)

print(f"Updated plugin_manifest.json with login plugin. Hash: {hash_hex}")
