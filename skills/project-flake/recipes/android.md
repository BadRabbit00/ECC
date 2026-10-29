# Android and Flutter apps

These are `kind = "app"` components: packages and checks, no image, no
module entry, no `checks.vm`.

## Gradle / Kotlin (reference: Nutritioner)

- SDK: `androidenv.composeAndroidPackages { platformVersions = [ "35" ];
  buildToolsVersions = [ "35.0.0" ]; includeEmulator = false; }`. The Android
  SDK is unfree and needs `android_sdk.accept_license = true`: ask first
  (`rule-nix-unfree-consent`), then set it in the single `import nixpkgs`.
- Dependencies offline through nixpkgs' gradle integration:
  `gradle.fetchDeps` with a `mitmCache` backed by `nix/deps.json`, and an
  `update-deps` package running `mitmCache.updateScript` so the lock is
  refreshed by a command, not by hand.
- APK derivation: `stdenv.mkDerivation` with `gradle` in `nativeBuildInputs`,
  `gradleFlags = [ "-Dorg.gradle.project.android.aapt2FromMavenOverride=${sdk}/…/aapt2" ]`,
  build task `assembleRelease`, `installPhase` copying the APK. Unit tests and
  lint as `checks.android` (Nutritioner runs both).
- Signing keys never go into the derivation: the release APK is unsigned,
  signing happens in CI with secrets from the CI environment.
- Emulator: a separate `devShells.emulator`, never part of `default`.

## Flutter (AAAG/DroneApp mobile apps)

- Desktop/web targets: `flutter.buildFlutterApplication { pubspecLock =
  lib.importJSON ./pubspec.lock.json; }` (convert `pubspec.lock` with
  `yq -o json`). This is the supported path in nixpkgs.
- Android APKs from Flutter are not reliably buildable inside the Nix sandbox.
  Keep the existing variant (Docker image `cirruslabs/flutter`), give the
  devShell `flutter` + the composed Android SDK for local builds, and record
  the app in `lib.components` with `package = null` and a comment why. Do not
  fake a derivation that downloads during the build.
