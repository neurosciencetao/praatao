# Non-invasive probe: ONLY report current selection. Never "select all".
# (Selecting all was flashing Praat's dynamic menus every poll.)
outPath$ = "D:/Documents/Playground/praatao/prototypes/v0/last_state.json"

nsel = numberOfSelected()
selItems$ = ""
for i to nsel
    lab$ = selected$(i)
    lab$ = replace$(lab$, """", "'", 0)
    if i > 1
        selItems$ = selItems$ + ", "
    endif
    selItems$ = selItems$ + "{""label"": """ + lab$ + """}"
endfor

nSound = numberOfSelected("Sound")
nTextGrid = numberOfSelected("TextGrid")

json$ = "{""selectedCount"": " + string$(nsel) + ", ""selectedSoundCount"": " + string$(nSound) + ", ""selectedTextGridCount"": " + string$(nTextGrid) + ", ""selected"": [" + selItems$ + "]}"
writeFileLine: outPath$, json$
