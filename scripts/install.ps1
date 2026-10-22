param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Remaining
)
py -3 (Join-Path $PSScriptRoot "install.py") @Remaining
exit $LASTEXITCODE
