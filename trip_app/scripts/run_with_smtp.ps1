# Lance le site en local avec un VRAI envoi d'e-mails par SMTP (par défaut : Outlook / Hotmail).
#
# Usage (depuis le dossier trip_app) :
#   powershell -ExecutionPolicy Bypass -File scripts\run_with_smtp.ps1
#
# L'adresse et le mot de passe sont demandés à chaque lancement. Ils ne sont ni affichés,
# ni écrits sur le disque, ni envoyés ailleurs qu'au serveur SMTP : ils ne vivent que
# dans cette fenêtre et disparaissent quand on la ferme.

param(
    [string]$SmtpHost = "smtp-mail.outlook.com",
    [int]$SmtpPort = 587
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

Write-Host "Envoi réel des e-mails via $SmtpHost (port $SmtpPort, chiffrement TLS)."
$address = Read-Host "Adresse e-mail d'envoi (ex. agence@outlook.com)"
$securePassword = Read-Host "Mot de passe (ou mot de passe d'application) de cette adresse" -AsSecureString
$credential = New-Object System.Management.Automation.PSCredential($address, $securePassword)

# Variables lues par config/settings.py, valables uniquement pour cette fenêtre.
$env:DJANGO_EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
$env:DJANGO_EMAIL_HOST = $SmtpHost
$env:DJANGO_EMAIL_PORT = "$SmtpPort"
$env:DJANGO_EMAIL_USE_TLS = "1"
$env:DJANGO_EMAIL_HOST_USER = $address
$env:DJANGO_EMAIL_HOST_PASSWORD = $credential.GetNetworkCredential().Password
# Outlook refuse un expéditeur différent du compte connecté.
$env:DJANGO_DEFAULT_FROM_EMAIL = $address

try {
    $test = Read-Host "Envoyer d'abord un e-mail de test à $address ? (o/n)"
    if ($test -eq "o") {
        python manage.py sendtestemail $address
        if ($LASTEXITCODE -eq 0) {
            Write-Host "E-mail de test envoyé : vérifiez la boîte de réception (et les indésirables)."
        }
        else {
            Write-Host "Échec de l'envoi : vérifiez l'adresse et le mot de passe. Si Outlook refuse la connexion, le compte n'accepte peut-être plus l'envoi par mot de passe."
            exit 1
        }
    }

    Write-Host "Site lancé sur http://127.0.0.1:8000/ (Ctrl+C pour arrêter)."
    python manage.py runserver
}
finally {
    # Efface le mot de passe de l'environnement, même en cas d'erreur ou d'arrêt par Ctrl+C.
    Remove-Item Env:DJANGO_EMAIL_HOST_PASSWORD -ErrorAction SilentlyContinue
}
