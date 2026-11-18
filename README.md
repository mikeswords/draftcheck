# Draftcheck

Draftcheck checks English writing for AI text signals and flags wording you might want to revisit. Use it for emails, articles, applications, and other drafts.

## Get started

1. Extract the ZIP if you received Draftcheck as an archive.
2. [Install uv](https://docs.astral.sh/uv/getting-started/installation/) if you need it.
3. On a Mac, double-click **Start Draftcheck.command** in Finder. It opens Draftcheck in your default browser.

Run these commands from the extracted **Draftcheck** folder in Terminal or PowerShell.

~~~sh
uv sync --locked --python 3.12
uv run --locked python -m draftcheck setup
uv run --locked python -m draftcheck serve --open
~~~

The first setup installs the Python dependencies and downloads about 81 MB of verified model files. After setup, reviews run on your device and work offline. Pasted text stays in your browser tab and in memory while a review runs. To stop Draftcheck, press Control+C in the terminal running it.

## Check a draft

Paste your text and select **Check draft**. Drafts shorter than 50 words get writing feedback. Drafts with at least 50 words also get an AI text signal on a 0 to 100 scale. For longer inputs, Draftcheck scores passages so the entire draft is covered.

The score is an estimate from [Deckard618's English Ettin 68M detector](https://huggingface.co/Deckard618/textdet). The app displays lower, uncertain, and higher bands using thresholds of 35 and 65. Treat these as screening signals. Real and AI-generated text can both be classified incorrectly, especially in short drafts.

## Use with ChatGPT or Codex

After checking a draft, select **Copy for ChatGPT** in the review panel to bring the writing notes into a chat. Personal installations with a local voice guide also offer a **Voice guide** button.

This command checks a file from Codex or a shell and returns JSON.

~~~sh
uv run --locked python -m draftcheck review "/absolute/path/to/draft.txt"
~~~

The review command also accepts text on standard input.
