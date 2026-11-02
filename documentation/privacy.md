---
state: production
layout: doc
eyebrow: Boring Steps
---

# Privacy Policy

The short version: reading collects nothing, so there is nothing to disclose.
Boring steps is a static site with no analytics, no trackers, and no ad
networks. Commenting on a post is optional and needs a sign-in; it is the only
feature that stores anything, and this page says exactly what. The page exists
to make these claims checkable rather than to ask permission for things the
site does not do.

## What the site does

Boring steps is plain HTML, CSS, and a little JavaScript, served as static
files. Reading a page sets no cookies, runs no analytics, and loads no
third-party scripts. The client-side code renders the page and the post list,
and on posts it fetches the published comments from the site's comments API.
That request carries no identifier; it asks only for the thread of the post you
are reading.

## Comments

Comments are optional. To post one, you sign in with one of five providers:
GitHub, LinkedIn, Amazon, Facebook, or Google. Sign-in goes through Amazon
Cognito, which handles the exchange with the provider; the site never sees your
password or the provider's secrets.

For each comment, the site stores:

- the subject identifier that Cognito assigns to your account (an opaque id),
- the display name your provider returns (an email-like name is replaced by
  "Reader"),
- the comment text,
- the time it was posted,
- its moderation status (approved, pending, or hidden).

These are stored so the comment can be shown with its author, attributed to the
right account for deletion, and moderated. No email address, IP address, or
browser details are stored with comments.

The Cognito user pool also keeps the email address your provider returns, as
part of your sign-in profile, when the provider shares one. It is never copied
into the comments table and never shown.

After sign-in, the page keeps the Cognito ID token in your browser's
`sessionStorage` for the current tab only; it is cleared when you sign out,
close the tab, or the token expires. The site itself sets no cookies. The
Cognito hosted sign-in page sets its own cookies on the Cognito domain, as part
of the sign-in flow.

## Retention and deletion

| Data | Kept |
| --- | --- |
| Comments | Until deleted on request or by moderation |
| Cognito profile (subject id, name, email) | Until the account is deleted |
| Write-limit counters | Expire automatically after the write window |
| Server logs | 30 days, with ids and outcomes only, no comment text |

To have your comments or your Cognito profile deleted, ask through one of the
contacts on the [About](/about) page (GitHub or LinkedIn), naming the post and
the provider you signed in with.

## What the host sees

Requesting a page tells the hosting provider (GitHub Pages) what any web
request tells any server: your IP address and the page you asked for. That is
infrastructure-level logging outside this site's control — not something Boring
steps collects, stores, or uses. The same holds for the AWS services that serve
the comments API and the sign-in page.

## The feed

The Atom feed at `/atom.xml` is a static file. Subscribing to it in a reader is
a request between your reader and the host; the site has no feed service and
keeps no subscriber list.

## Children's privacy

The site is not directed at children and knowingly collects nothing from anyone
of any age. Commenting requires an account with one of the providers above,
under that provider's own age rules.

## Changes

If anything about the site's data handling changes, this page is updated
before that change ships. Adding optional, sign-in comments was such a change.
There is no mailing list; check back here.
