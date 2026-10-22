param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Remaining
)
py -3 (Join-Path $PSScriptRoot "sync_project.py") @Remaining
exit $LASTEXITCODE
