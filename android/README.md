# 한끼AI Android APK

This is a **WebView wrapper APK** around the working demo:

- App name: `한끼AI`
- Package: `com.hankki.ai`
- Min Android: 7.0 (API 24)
- Target: Android 15 (API 35)
- Size: ~17KB (no bundled model; AI runs on the demo server)
- Signed with a debug key (installable, not Play Store-ready)

## Install

1. Copy `한끼AI_Android.apk` to the phone (KakaoTalk/Telegram/USB/Google Drive).
2. On the phone, allow **Install unknown apps** for the app you used to open the file.
3. Tap the APK → Install → Open.
4. Keep internet on. The app loads the demo server URL stored in `MainActivity.java`.

If the server/tunnel is down, the app shows a “서버에 연결할 수 없어요” page with a retry button.

## Important: the APK points to the current demo tunnel

`MainActivity.java`:

```java
private static final String APP_URL = "https://rabbit-hans-happen-europe.trycloudflare.com/";
```

Cloudflare quick tunnels are temporary. If the tunnel changes, rebuild the APK with the new URL:

```powershell
# edit APP_URL first
powershell -ExecutionPolicy Bypass -File build_apk.ps1
```

The output is `HankkiAI/HankkiAI-debug.apk`.

## Rebuild from source

The project is built **without Gradle/Android Studio** using Android SDK build-tools directly.

Requirements:

- JDK 17 (already under `android/jdk17/` in this workspace)
- Android SDK build-tools 35 (`android/sdk_tmp/android-15/`)
- Android platform 35 `android.jar` (`android/sdk_tmp/android-35/android.jar`)

Build:

```powershell
cd android
powershell -ExecutionPolicy Bypass -File build_apk.ps1
```

The script runs:

1. `aapt2 compile` resources
2. `aapt2 link` manifest + resources
3. `javac` MainActivity + R.java
4. `d8` to `classes.dex`
5. `jar` + `zipalign`
6. `apksigner` with `debug.keystore`

## Files

```text
android/
  HankkiAI/
    AndroidManifest.xml
    src/com/hankki/ai/MainActivity.java
    res/values/strings.xml
    res/drawable/ic_launcher.png
    HankkiAI-debug.apk
  build_apk.ps1
  README.md
```

## PWA alternative

The same app is a PWA. On Android Chrome, open the demo URL and choose **홈 화면에 추가 / Add to Home screen** — no APK, same UI. The APK is for “installable file” submission requirements.

## Limitations

- It is a WebView, not a native app. It needs the demo server for AI/API.
- The model is not bundled in the APK. A fully offline model would require converting CLIP/YOLO to TFLite/ONNX and bundling ~100–300MB.
- Debug signature is fine for class demo; for Play Store, generate a release keystore and build a release APK/AAB.
