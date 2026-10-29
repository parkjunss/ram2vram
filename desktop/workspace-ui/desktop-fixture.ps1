param([string]$OutputFile)
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
Add-Type -Path (Join-Path $PSScriptRoot '../strata/apps/host/server/agent/desktop-native.cs')
$form=New-Object System.Windows.Forms.Form
$form.Text='RAM2VRAM Synthetic Desktop Test';$form.Width=550;$form.Height=300;$form.StartPosition='CenterScreen'
$inputBox=New-Object System.Windows.Forms.TextBox;$inputBox.Location=New-Object System.Drawing.Point(30,40);$inputBox.Width=400;$inputBox.AccessibleName='Synthetic input'
$button=New-Object System.Windows.Forms.Button;$button.Text='Synthetic save';$button.Location=New-Object System.Drawing.Point(30,100);$button.Width=200
$button.Add_Click({[System.IO.File]::WriteAllText($OutputFile,$inputBox.Text)})
$form.Controls.Add($inputBox);$form.Controls.Add($button)
$form.Add_Shown({[void][RDesktop]::ShowWindow($form.Handle,5)})
$timer=New-Object System.Windows.Forms.Timer;$timer.Interval=120000;$timer.Add_Tick({$form.Close()});$timer.Start()
[void]$form.ShowDialog()
