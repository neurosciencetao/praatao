# Praatao semantic state probe.
#
# Writes a tab-separated dump of Praat's semantic state to the file whose
# path replaces the @OUT@ placeholder.  The file is parsed by
# praatao.sensors.praat_state.parse_probe_output().
#
# Probe output format (one record per line, fields separated by a TAB):
#
#   V<TAB><praat version>              Praat version, e.g. 6.4.12
#   N<TAB><number of selected objects>  size of the current selection
#   S<TAB><object id><TAB><full name>   one line per selected object
#                                      (id = Praat object id, full name =
#                                       "<Type> <name>", e.g. "Sound demo_vowel")
#   A<TAB><duration><TAB><sampling freq><TAB><channels><TAB><start><TAB><end>
#                                      attributes of a single selected Sound
#   T<TAB><number of tiers>             tiers of the selected TextGrid (if any)
#   I<TAB><tier index><TAB><tier name>  one line per tier
#   E                                 end-of-probe marker
#
# The probe is strictly read-only: it never changes the selection.  The full
# list of objects is *not* available from Praat's scripting language (there
# is no numberOfObjects() and object[i] exposes numbers only), so that part
# is read from the Objects window through UI Automation.
#
# IMPORTANT: a failing Praat script pops up a modal error box in the running
# Praat GUI, which then blocks every later --send call.  Every command below
# is therefore guarded so that it cannot fail for any selection state.
# (Praat has no backslash escapes in string literals, so "\t" below is a
# backslash followed by a letter, used as our escape marker.)

out$ = "@OUT@"
deleteFile: out$
appendFileLine: out$, "V" + tab$ + praatVersion$

nsel = numberOfSelected()
ntg = numberOfSelected("TextGrid")
appendFileLine: out$, "N" + tab$ + string$(nsel)

for i from 1 to nsel
    nm$ = selected$(i)
    nm$ = replace$(nm$, "\", "\\", 0)
    nm$ = replace$(nm$, tab$, "\t", 0)
    nm$ = replace$(nm$, newline$, "\n", 0)
    appendFileLine: out$, "S" + tab$ + string$(selected(i)) + tab$ + nm$
endfor

# Attributes of the selection.  Praat's "Get ..." commands only work on a
# single selected object of the right type, and they refuse the command
# otherwise, so every case is guarded separately.
if nsel = 1
    full$ = selected$()
    type$ = extractWord$(full$, "")
    if type$ = "Sound"
        dur = Get duration
        sr = Get sampling frequency
        ch = Get number of channels
        st = Get start time
        et = Get end time
        appendFileLine: out$, "A" + tab$ + string$(dur) + tab$ + string$(sr) + tab$ + string$(ch) + tab$ + string$(st) + tab$ + string$(et)
    endif
    if type$ = "TextGrid"
        ntiers = Get number of tiers
        appendFileLine: out$, "T" + tab$ + string$(ntiers)
        for i from 1 to ntiers
            tier$ = Get tier name: i
            tier$ = replace$(tier$, "\", "\\", 0)
            tier$ = replace$(tier$, tab$, "\t", 0)
            tier$ = replace$(tier$, newline$, "\n", 0)
            appendFileLine: out$, "I" + tab$ + string$(i) + tab$ + tier$
        endfor
    endif
endif

appendFileLine: out$, "E"
