# Load demo sound only if not already present (avoids duplicates on repeated clicks).
demoPath$ = "D:/Documents/Playground/praatao/prototypes/v0/assets/demo_vowel.wav"
select all
nSound = numberOfSelected("Sound")
if nSound < 1
    Read from file: demoPath$
else
    # Keep an existing Sound selected for the coach flow
    selectObject: selected#()
endif
