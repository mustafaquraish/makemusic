

Okay, let's take the web app for viewing the notes and make it fully production ready. I have a bunch of features I want to add, and a bunch of bugBugs that need to be fixed. But before we do that, I want you to make sure that everything is being absolutely and completely tested. It is paramount that you have complete end-to-end UI tests and that every single feature is properly and thoroughly tested. Take screenshots, add logs, test layouts, do whatever you need to do, but make sure that stuff is working before I have to tell you that it doesn't work. Remember, you are responsible for this and do not rely on the user to tell you if something is wrong. Anything that could potentially go wrong should be checked. I need an extremely thorough test plan and a bunch of UI tests.

Use something like playwright which is set up. Remember to be thorough and systematic. You should make sure everything looks visually like you intend and functions consistently and perfectly.

Now, some bugs / quirks in the current UI:
- Arrow keys to scroll doesn't work when playing, only when paused.
- The app is not very mobile friendly - the buttons in the top UI are really small and hard to interact with
- On mobile, I can't zoom with pinching
- The speed / hand controls on desktop are also too small, I would like some better UI
- Would like the piano to be a little taller on desktop especially.


Features:
- Make this a more general application - not a static viewer for a single song. More detailed features below.
- Should allow loading in any JSON file
- Want this to be more of an editor than just a viewer. I want to have an "edit" mode that lets me visually modify, add or correct notes. This is important because the pipeline isn't perfect and I want to be able to fix mistakes or add notes that were missed.
- I want to be able to add "markers" to the timeline. These are just horizontal lines with labels that I can use to mark important sections of the song (like verse, chorus, etc) or just to leave notes for myself.
- I should be able to easily jump to markers and resume playback from there.
- I want to be able to export the modified JSON after editing - and reimport it later. I want it to be backward compatible - so all the metadata should be treated as optional and should be preserved if present, but it shouldn't be required for the viewer to work.
- For each note, it would be nice to have a semi-transparent line going from the bottom of the note down to the keyboard, so it's easier to see which key it corresponds to, especially when zoomed out.
- Would be nice to have the sharp/flat notes be slightly different colors than the natural notes, to make them easier to distinguish at a glance. Also they should be slightly smaller than the natural notes, similar to how those keys are smaller on a real piano.
- Add a command palette that can be opened with Cmd+P, and all possible actions / shortcuts / functionality / toggles etc should be accessible, fuzzy searchable, and selectable from there. Keyboard accessibility is **super** important, and you should make sure ALL your designs are fully navigable and usable with just a keyboard. This is a must.


For each of the above features - you MUST add comprehensive tests for EACH ONE. Here is the process you should undertake (a meta-program for you, the AI agent, to follow):

```
add_tests_for_existing_code
run_tests
if saw any failures:  # should expect to see some quirks or bugs here, especially with the UI tests
    - fix existing code until all tests pass

# moving on...
while bugs/features left:  # from mentioned above
    - Pick most important bug/feature to work on next (prioritize based on user impact, then ease of implementation)
    - Implement the bug fix / feature
    - For this particular bug/feature, add comprehensive tests covering all edge cases and scenarios
    - Run tests
    - If any tests fail, fix the code until all tests pass
    - ONLY ONCE ALL TESTS PASS, move on to the next bug/feature. This is crucial - do not move on until you have verified that your implementation is correct and does not break anything else. WE WANT 100% TEST PASSING ALL THE TIME.

# Once all bugs/features are finished
while true:   # Keep going until interrupted - the user will stop you when they are done. We are targetting asynchronous work queueing.
    - sleep for 5 minutes
    - open ./REMAINING.md, and read any additional requests queued by the user
    - work on each request, in similar fashion to above.

```

This is extremely important since we do not want to leave the repository in a completely broken state. Do NOT try to tackle multiple features/bugs at once without testing in between. This is a common mistake that can lead to a broken codebase and makes it very hard to identify which change caused the breakage. Always make sure to have a green test suite before moving on to the next change.


Again, please remember that you are responsible for this application and you should be putting complete polish on this. In the current version of the application there are many features that don't work well with each other. For example, the scrolling is inconsistent between mobile and desktop and then even there it is inconsistent between playing and not playing with the arrow keys and the mouse. We don't want any of this. For every single feature, please take a systematic approach. Step back, look at the entire problem space and come up with the best, most cohesive solution. There should be one ground truth for handling scrolling or any such mechanism, for example. Don't introduce any bugs, don't special case anything. Try and make your solutions as generalizable as possible to minimize the surface area for bugs and then test every single part of those


Do not stop to ask the user if they are sure or want to continue. You should keep going until you are interrupted. You are an autonomous agent.