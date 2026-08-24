# Crabbiq — Supported Site Strategy

Crabbiq uses a layered resolver architecture rather than hard-coding a small list of domains.

## Coverage

The resolver should attempt, in order:

1. Direct media/file URLs
2. yt-dlp extractors and generic extractor
3. Dedicated file-host adapters
4. HLS/DASH manifest resolution
5. Image/media page discovery
6. Authorized authenticated-session handling where supported

## Social / video platforms

YouTube, YouTube Music, YouTube Shorts, Instagram, Facebook, TikTok, X/Twitter, Reddit, Vimeo, Twitch, Dailymotion, Snapchat, Pinterest, LinkedIn, Tumblr, VK, Rutube, OK.ru, Bilibili, Streamable, Rumble, Kick, Mixcloud, SoundCloud, Bandcamp, Audiomack, Veoh, BitChute, PeerTube, Odysee, DTube, Coub, Flickr, Imgur, Gfycat-compatible sources, TED, TEDx, Khan Academy, Coursera-compatible public media, Internet Archive, NASA, C-SPAN, PBS, BBC, CNN and other extractors provided by the active extraction engine.

## File hosts / download hosts

Way2Share, Keep2Share, 1fichier, MediaFire, Pixeldrain, GoFile, File.io-compatible links, Krakenfiles, AnonFiles-compatible mirrors when operational, Ulož.to-compatible services, KatFile, Turbobit, NitroFlare, RapidGator, Uploaded-compatible services, SendSpace, Zippyshare-compatible mirrors, Mega-compatible public links, Dropbox public links, Google Drive public links, OneDrive public links, Box public links and other file-host services for which a maintained resolver exists.

Availability varies by service, account type, geography, authentication, quotas, CAPTCHAs, site changes and the active extractor version.

## Important implementation rule

Do not claim universal support merely because a domain is in this document. A URL is considered supported only after the resolver successfully discovers media/file metadata. Unsupported, expired, private, DRM-protected, CAPTCHA-blocked or otherwise inaccessible URLs must return a truthful diagnostic state.

## Maintenance

The production backend should regularly update its extraction engine, run automated smoke tests against representative public URLs, isolate extraction jobs, sanitize filenames, constrain subprocess arguments, enforce timeouts, and prevent arbitrary URL input from becoming shell commands.

This project does not implement bypasses for DRM, paywalls, CAPTCHAs, authentication controls, or other access restrictions. Authorized session/cookie support may be provided where appropriate.
