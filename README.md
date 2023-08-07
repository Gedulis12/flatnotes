![Logo](docs/logo.svg)

A self-hosted, database-less note taking web app that utilises a flat folder of markdown files for storage.

Log into the [demo site](https://demo.flatnotes.io) and take a look around. *Note: This site resets every 15 minutes.*


## Design Principle

flatnotes is designed to be a distraction free note taking app that puts your note content first. This means:

* A clean and simple user interface.
* No folders, notebooks or anything like that. Just all of your notes, backed by powerful search and tagging functionality.
* Quick access to a full text search from anywhere in the app (keyboard shortcut "/").

Another key design principle is not to take your notes hostage. Your notes are just markdown files. There's no database, proprietary formatting, complicated folder structures or anything like that. You're free at any point to just move the files elsewhere and use another app.

Equally, the only thing flatnotes caches is the search index and that's incrementally synced on every search (and when flatnotes first starts). This means that you're free to add, edit & delete the markdown files outside of flatnotes even whilst flatnotes is running.

## Features

* Mobile responsive web interface.
* Raw/WYSIWYG markdown editor modes.
* Advanced search functionality.
* Note "tagging" functionality.
* Light/dark themes.
* Multiple authentication options (none, username/password, 2FA).
* Restful API.

See [the wiki](https://github.com/Dullage/flatnotes/wiki) for more details.

## Installation

The easiest way to install flatnotes is using Docker.

### Example Docker Run Command

```shell
docker run -d \
  -e "PUID=1000" \
  -e "GUID=1000" \
  -e "FLATNOTES_AUTH_TYPE=password" \
  -e "FLATNOTES_USERNAME=user" \
  -e "FLATNOTES_PASSWORD=changeMe" \
  -e "FLATNOTES_SECRET_KEY=aLongRandomSeriesOfCharacters" \
  -v "$(pwd)/data:/data" \
  -p "8080:8080" \
  dullage/flatnotes:latest
```

### Example Docker Compose
```yaml
version: "3"

services:
  flatnotes:
    container_name: flatnotes
    image: dullage/flatnotes:latest
    environment:
      PUID: 1000
      GUID: 1000
      FLATNOTES_AUTH_TYPE: "password"
      FLATNOTES_USERNAME: "user"
      FLATNOTES_PASSWORD: "changeMe!"
      FLATNOTES_SECRET_KEY: "aLongRandomSeriesOfCharacters"
    volumes:
      - "./data:/data"
      # Optional. Allows you to save the search index in a different location: 
      # - "./index:/data/.flatnotes"
    ports:
      - "8080:8080"
    restart: unless-stopped
```

See the [Environment Variables](https://github.com/Dullage/flatnotes/wiki/Environment-Variables) article in the wiki for a full list of configuration options.


## Roadmap

I want to keep flatnotes as simple and distraction free as possible which means limiting new features. This said, I welcome feedback and suggestions.

One feature I do plan to implement is the ability to *share* a note. In the spirit of simple and database-less, the current plan is to generate temporary pre-signed URLs but this needs to be explored.


## Sponsorship

If you find this project useful, please consider buying me a beer. It would genuinely make my day.

[![Sponsor](https://img.shields.io/static/v1?label=Sponsor&message=%E2%9D%A4&logo=GitHub&color=%23fe8e86)](https://github.com/sponsors/Dullage)


## Thanks

A special thanks to 2 fantastic open source projects that make flatnotes possible.

* [Whoosh](https://whoosh.readthedocs.io/en/latest/intro.html) - A fast, pure Python search engine library.
* [TOAST UI Editor](https://ui.toast.com/tui-editor) - A GFM Markdown and WYSIWYG editor for the browser.
