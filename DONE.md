
1. Tests for each feature should be comprehensive. We specifically want:
  - 100% coverage of the code - every feature, code path and edge case must be tested.
  - Test with different notes, number of notes, note durations, key ranges, and both hands.
  - Test the summary statistics for accuracy.
  - _try_ to break the features. Try to come up with weird edge cases that might cause bugs and make sure those are tested as well. You are trying to make the application secure, so use a subagent to come up with a bunch of valid but "almost malicious" test cases that might cause issues and make sure those are tested as well, then fix those.

2. Needs an "export" or "save" button

3. When opening the app, currently I _have_ to upload a JSON. Would be nice to have the option to go to an empty project as well (in edit mode) so I can just make something manually to export.


- In editing mode: I can't seem to pick which hand I want to assign the note to. It seems to pick based on the note, which is weird. I am also unable to change it. Please come up with an intuitive way to do this. How do other editors handle things like this?

- In editing mode: clicking adds a note of a fixed size. Ideally, it would be nice to be able to click-and-drag to decide the size of the note when placing it, instead of having it be 2 separate actions

- When I open up a new project, there are no "tracks" (vertical lines) visible at all until I add a new note. This is a little weird and makes it hard for me to see which note might be added when i click.

- In edit mode, would be nice if I could right click on a note to get some options like delete note etc. It was unclear to me how to delete a note, i had to randomly try pressing buttons. The UI should be more intuitive about this as well, and should be mouse accessible too.

- Would be nice to have a settings panel I can open. This should be a modal that has various toggles and settings for the viewer. For example, I might want to toggle on/off the lines connecting notes to the keyboard, or I might want to change the colors used for left/right hand notes, or I might want to change the zoom level or scroll speed. These should all be in a settings panel that can be easily accessed. These settings should also be saved in localStorage so they persist across sessions.

- For the lines connecting notes to the keyboard, they are helpful now but visually very noisy since we have lines for every note that exists in the whole song. It would be nice to only show this for the currently visible notes and not all of them. Maybe we could fade them in so we don't get jarring lines popping in and out as we scroll. This would be a nice improvement to reduce visual clutter.

- Lastly - major feature. It would be nice to have a "backend" so the user can save / edit / reload files from the app without having to go through their computer. However, this is a static app with no backend, and we don't have a database. One idea here is to use GitHub as a backend - the user can authenticate with their Github account, and give access to creating/writing to a repo. Then, when they save a file, it creates a new file in that repo with the JSON content. Then they can load files from that repo as well. This way we get a "backend" without having to actually build one. Be mindful to not rely on having any custom backend server for us - this is a free utility with no hosting costs, so we want to avoid any dependencies on custom backend infrastructure. The UI should _clearly_ explain to a user how to sign in, but this should be completely optional.

   - I am also unfamiliar with how to help you set this up. After you have implemented, i suspect you'd need some keys / actions from me to register the app or whatever with github. Please leave detailed instructions for me in ./SETUP_GH.md. Feel free to explore the internet for guides and refer to those if needed.