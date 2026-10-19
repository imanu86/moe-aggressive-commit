#!/bin/bash
# 19/10: stato di Jump Desktop (JumpConnect in sessione 1, CPU cumulativa): la cattura gira sulla 2080 Ti, condizione non standard
powershell -NoProfile -Command "\$p=Get-Process JumpConnect -EA SilentlyContinue | ?{\$_.SessionId -eq 1}; if(\$p){'JUMP connesso: ' + ((\$p|%{'pid {0} cpu {1:N1}s' -f \$_.Id,\$_.CPU}) -join ', ')} else {'JUMP assente'}"
