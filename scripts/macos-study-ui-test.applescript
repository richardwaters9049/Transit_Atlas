on run argv
  set phase to item 1 of argv
  set studyPath to item 2 of argv
  set outputFolder to ""
  if phase is "save" then set outputFolder to item 3 of argv

  tell application "System Events" to tell process "transit-atlas" to set frontmost to true

  if phase is "save" then
    my waitForText("K00115.03", 60)
    my saveStudyToFolder(outputFolder)
    my waitForText("Saved K00115.03.atlas.json", 30)
    return "PASS: study saved through the native macOS Save dialog."
  else if phase is "restore" then
    my changeCandidate("K00005.01")
    my waitForText("K00005.01", 45)
    my waitForText("K01090.01", 45)
    my openStudyAtPath(studyPath)
    my waitForText("Opened study for K00115.03", 60)

    set candidateValue to my queryValue()
    if candidateValue is not "K00115.03" then error "Successful replay did not restore the candidate; found " & candidateValue
    set visibleText to my appText()
    my assertContains(visibleText, "Candidate · K00115.03")
    my assertContains(visibleText, "Reference · K02961.01")
    my assertContains(visibleText, "4,108/4,159 cadences")
    my assertContains(visibleText, "kplr009579641-2010078095331_llc.fits")
    my assertContains(visibleText, "kplr010471515-2010078095331_llc.fits")
    return "PASS: native Open restored K00115.03, K02961.01, both Q4 light-curve products and their cadence summaries."
  else if phase is "failure" then
    my changeCandidate("K00005.01")
    my waitForText("K00005.01", 45)
    my waitForText("K01090.01", 45)
    my openStudyAtPath(studyPath)
    my waitForText("processing fingerprints differ", 60)

    set candidateValue to my queryValue()
    if candidateValue is not "K00005.01" then error "Failed replay changed the active candidate; found " & candidateValue
    set visibleText to my appText()
    my assertContains(visibleText, "K00005.01 ·")
    my assertContains(visibleText, "Distance to K01090.01")
    return "PASS: tampered light-curve fingerprint was rejected and K00005.01 with its distance breakdown remained active."
  else
    error "Unknown test phase: " & phase
  end if
end run

on appText()
  tell application "System Events" to tell process "transit-atlas"
    set frontmost to true
    try
      tell window "Transit Atlas"
        set elements to entire contents of scroll area 1 of group 1 of group 1
        set outputText to ""
        repeat with elementRef in elements
          try
            if role of elementRef is "AXStaticText" then
              set currentValue to value of elementRef
              if currentValue is not missing value then set outputText to outputText & (currentValue as text) & linefeed
            end if
          end try
        end repeat
        return outputText
      end tell
    on error
      return ""
    end try
  end tell
end appText

on waitForText(expectedText, timeoutSeconds)
  repeat with attempt from 1 to (timeoutSeconds * 2)
    set currentText to my appText()
    if currentText contains expectedText then return currentText
    delay 0.5
  end repeat
  error "Timed out waiting for app text: " & expectedText
end waitForText

on assertContains(haystack, needle)
  if haystack does not contain needle then error "Expected app text was missing: " & needle
end assertContains

on queryValue()
  tell application "System Events" to tell process "transit-atlas"
    set frontmost to true
    tell window "Transit Atlas"
      return value of text field "CANDIDATE KOI" of group 1 of group 2 of UI element 1 of scroll area 1 of group 1 of group 1
    end tell
  end tell
end queryValue

on changeCandidate(candidateId)
  tell application "System Events" to tell process "transit-atlas"
    set frontmost to true
    tell window "Transit Atlas"
      set queryField to text field "CANDIDATE KOI" of group 1 of group 2 of UI element 1 of scroll area 1 of group 1 of group 1
      click queryField
      keystroke "a" using {command down}
      set previousClipboard to the clipboard
      set the clipboard to candidateId
      keystroke "v" using {command down}
      set the clipboard to previousClipboard
      delay 0.2
      click button "FIND NEIGHBOURS" of group 1 of group 2 of UI element 1 of scroll area 1 of group 1 of group 1
    end tell
  end tell
end changeCandidate

on saveStudyToFolder(outputFolder)
  tell application "System Events" to tell process "transit-atlas"
    set frontmost to true
    tell window "Transit Atlas"
      click button "SAVE STUDY" of group 1 of UI element 1 of scroll area 1 of group 1 of group 1
    end tell
    delay 1
    keystroke "g" using {command down, shift down}
    delay 0.5
    keystroke outputFolder
    delay 0.2
    keystroke return
    delay 0.8
    keystroke return
  end tell
end saveStudyToFolder

on openStudyAtPath(studyPath)
  tell application "System Events" to tell process "transit-atlas"
    set frontmost to true
    tell window "Transit Atlas"
      click button "OPEN STUDY" of group 1 of UI element 1 of scroll area 1 of group 1 of group 1
    end tell
    delay 1
    keystroke "g" using {command down, shift down}
    delay 0.5
    keystroke studyPath
    delay 0.2
    keystroke return
    delay 0.8
    keystroke return
  end tell
end openStudyAtPath
