from string import Template

fmt_4 = Template("""
igntype=4
&aeriallist
naerial=$n_rows
targettemp=1000.0
ramprate=172.00
/
$rows
""")

fmt_5 = Template("""
igntype=5
&atvlist
natv=$n_rows
targettemp=1000.0
flamedistance=4.00
/
$rows
""")
