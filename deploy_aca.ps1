$ErrorActionPreference = "Continue"
$env:AZURE_CORE_ONLY_SHOW_ERRORS = "True"

function Assert-Success {
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Islem basarisiz oldu. Hata kodu: $LASTEXITCODE"
        exit $LASTEXITCODE
    }
}

$ACR_NAME = "sartname"
$RG_NAME = "Sartname"
$APP_NAME = "sartnameai-app"
$ENV_NAME = "sartnameai-env"
$IMAGE_TAG = "v7"
$IMAGE_NAME = "$($ACR_NAME).azurecr.io/sartnameai:$IMAGE_TAG"
$LOCATION = "polandcentral"

Write-Host "1. ACR Kimlik Bilgileri Aliniyor..."
$ACR_PASSWORD = (az acr credential show -n $ACR_NAME --query "passwords[0].value" -o tsv --only-show-errors).Trim()
Assert-Success

Write-Host "2. Docker Login Yapiliyor..."
$ACR_PASSWORD | docker login "$($ACR_NAME).azurecr.io" -u $ACR_NAME --password-stdin
Assert-Success

Write-Host "3. Docker Image Build ($IMAGE_TAG)..."
docker build -t $IMAGE_NAME .
Assert-Success

Write-Host "4. Docker Push Yapiliyor..."
$pushSuccess = $false
for ($i = 1; $i -le 5; $i++) {
    Write-Host "Docker Push denemesi $i/5..."
    docker push $IMAGE_NAME
    if ($LASTEXITCODE -eq 0) {
        $pushSuccess = $true
        break
    }
    Write-Host "Baglanti zaman asimina ugradi veya hata alindi, 3 saniye icinde kaldigi yerden devam ediliyor..."
    Start-Sleep -Seconds 3
}
if (-not $pushSuccess) {
    Write-Error "Docker push islemi tamamlanamadi."
    exit 1
}

Write-Host "5. .env Degiskenleri Okunuyor..."
$envFile = ".env"
$envVars = @()
foreach($line in Get-Content $envFile) {
    if ($line -match "^([^#\s=]+)=(.*)$") {
        $key = $matches[1].Trim()
        $val = $matches[2].Trim()
        if ($val -ne "") {
            $envVars += "$key=$val"
        }
    }
}

Write-Host "6. Container App Guncelleniyor (v3 Birlesik FastMCP)..."
$argsList = @("containerapp", "update", "-n", $APP_NAME, "-g", $RG_NAME, "--image", $IMAGE_NAME, "--set-env-vars") + $envVars + @("--only-show-errors")
az @argsList
Assert-Success

$FQDN = (az containerapp show -n $APP_NAME -g $RG_NAME --query properties.configuration.ingress.fqdn -o tsv --only-show-errors).Trim()
Write-Host "---------------------------------------------------------"
Write-Host "TUM ISLEMLER BASARIYLA TAMAMLANDI!"
Write-Host "CANLI UYGULAMA URL: https://$FQDN"
Write-Host "---------------------------------------------------------"
