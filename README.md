Python app to generate all potential card combinations of a given deck with a provided hand size.
Comes preloaded with a standard 52-card deck but allows loading a custom deck via csv.

Will cache all deck and hand size combinations for larger combo counts (up to 750M combinations) to allow for faster re-filtering with parallel processing.

**How to get started:**
1. Navigate to the [Releases](http://www.github.com/Soulsbane96/card-hand-probability-analyzer/releases/) page.
2. Find the release labeled "Latest".
3. Download HandProbabilityAnalyzer_v{version_number}.zip from the Assets section of that release.
    - Subsequent updates will ask to be downloaded and auto-update in place when a new release version is created.
4. Extract the zip contents wherever you would like, including the /themes and /deck-cache folders.
5. Run HandProbabilityAnalyzer.exe

**Usage**
1. Run the exe.
2. Choose your deck, either the built in 52-card deck or your own custom deck csv. CSV header rows should be the attributes you'll want to filter or find statistics of.  
    - i.e. "Rank", "Suit", "Color", etc.
3. Choose a hand size and click Load Deck.
4. Build your filter criteria (these will be highlighted when the results are generated).
5. Run Analysis. This will generate a combination for each possible distinct hand of the given hand size. 
    - Duplicated cards in a csv will show up as different cards in these combinations. If you do not want this you'll need to pare down to one row per card.

*Created with the assistance of Claude Code.*
