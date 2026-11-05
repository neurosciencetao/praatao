# probe_selected.praat
# Spike A: write selected-object summary for Praatao.
# Run:
#   .\Praat.exe --send "D:\Documents\Playground\praatao\prototypes\probe\probe_selected.praat"
#
# Note: Praat string APIs differ slightly by version — verify once on your build.

outPath$ = "D:/Documents/Playground/praatao/prototypes/probe/last_state.json"

n = numberOfSelected()
line$ = "{""selectedCount"": " + string$(n) + ", ""items"": ["

for i to n
    # selected$(i) ≈ "Type name" (type then object name)
    item$ = selected$(i)
    if i > 1
        line$ = line$ + ", "
    endif
    line$ = line$ + """" + item$ + """"
endfor

line$ = line$ + "]}"
writeFileLine: outPath$, line$
