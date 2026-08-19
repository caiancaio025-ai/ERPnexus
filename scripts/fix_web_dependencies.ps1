$ErrorActionPreference = "Stop"
$webPath = Join-Path (Split-Path $PSScriptRoot -Parent) "apps\web"
Push-Location $webPath
try {
  npm config set registry https://registry.npmjs.org/
  npm install
  npm ls lucide-react
} finally {
  Pop-Location
}
