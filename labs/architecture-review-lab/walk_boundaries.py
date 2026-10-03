from boundaries import changed, fixture, inspect

design = fixture()
print(inspect(design))

export_writes_order = changed(design, "foreign-write")
print(inspect(export_writes_order))

export_reads_internal = changed(design, "internal-import")
print(inspect(export_reads_internal))

back_reference = changed(design, "cycle")
print(inspect(back_reference))
