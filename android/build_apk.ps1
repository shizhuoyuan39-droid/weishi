param(
  [string]$Project = "$PSScriptRoot\HankkiAI"
)
$ErrorActionPreference = "Stop"
$androidRoot = $PSScriptRoot
$jdk = Get-ChildItem "$androidRoot\jdk17" -Directory | Where-Object { Test-Path (Join-Path $_.FullName "bin\javac.exe") } | Select-Object -First 1
$bt = "$androidRoot\sdk_tmp\android-15"
$platform = "$androidRoot\sdk_tmp\android-35\android.jar"
if (-not $jdk) { throw "JDK17 not found under $androidRoot\jdk17" }
$jdkHome = $jdk.FullName
if (-not (Test-Path "$jdkHome\bin\javac.exe")) { throw "javac not found under $jdkHome" }
if (-not (Test-Path "$bt\aapt2.exe")) { throw "build-tools not found under $bt" }
if (-not (Test-Path $platform)) { throw "android.jar not found at $platform" }

$env:JAVA_HOME = $jdkHome
$env:PATH = "$jdkHome\bin;$bt;$env:PATH"

Set-Location $Project
Remove-Item -Recurse -Force "build_apk" -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path "build_apk\gen","build_apk\classes","build_apk\dex" | Out-Null

Write-Host "1/6 aapt2 compile"
& "$bt\aapt2.exe" compile --dir res -o "build_apk\compiled.zip"
if ($LASTEXITCODE -ne 0) { throw "aapt2 compile failed" }

Write-Host "2/6 aapt2 link"
& "$bt\aapt2.exe" link -o "build_apk\base.apk" -I $platform --manifest AndroidManifest.xml -R "build_apk\compiled.zip" --java "build_apk\gen" --auto-add-overlay --min-sdk-version 24 --target-sdk-version 35
if ($LASTEXITCODE -ne 0) { throw "aapt2 link failed" }

Write-Host "3/6 javac"
& "$jdkHome\bin\javac.exe" -encoding UTF-8 -source 8 -target 8 -classpath $platform -d "build_apk\classes" "src\com\hankki\ai\MainActivity.java" "build_apk\gen\com\hankki\ai\R.java"
if ($LASTEXITCODE -ne 0) { throw "javac failed" }

Write-Host "4/6 d8"
& "$bt\d8.bat" --lib $platform --min-api 24 --output "build_apk\dex" "build_apk\classes\com\hankki\ai\MainActivity.class" "build_apk\classes\com\hankki\ai\R.class"
if ($LASTEXITCODE -ne 0) { throw "d8 failed" }

Write-Host "5/6 package + zipalign"
& "$jdkHome\bin\jar.exe" uf "build_apk\base.apk" -C "build_apk\dex" classes.dex
& "$bt\zipalign.exe" -f 4 "build_apk\base.apk" "build_apk\aligned.apk"
if ($LASTEXITCODE -ne 0) { throw "zipalign failed" }

Write-Host "6/6 sign"
$ks = "$Project\debug.keystore"
if (-not (Test-Path $ks)) {
  & "$jdkHome\bin\keytool.exe" -genkeypair -v -keystore $ks -storepass android -alias androiddebugkey -keypass android -keyalg RSA -keysize 2048 -validity 10000 -dname "CN=Android Debug,O=Android,C=US" | Out-Null
}
& "$bt\apksigner.bat" sign --ks $ks --ks-pass pass:android --key-pass pass:android --out "HankkiAI-debug.apk" "build_apk\aligned.apk"
if ($LASTEXITCODE -ne 0) { throw "apksigner failed" }
& "$bt\apksigner.bat" verify --print-certs "HankkiAI-debug.apk"

Write-Host "APK: $Project\HankkiAI-debug.apk"

