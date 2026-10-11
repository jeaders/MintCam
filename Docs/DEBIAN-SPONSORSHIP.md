# Getting MintCam into Debian (and from there into Ubuntu and the Mint Store)

The ubuntu-motu reply pointed at the right thing: Debian first, Ubuntu imports
it automatically, and the Linux Mint Software Manager shows everything that
comes from Ubuntu. This is the route with a working review process for first
time packagers.

Everything below is already prepared: the source package is built and
`lintian`-clean, `~/.dput.cf` has the `mentors` section.

## 0. One thing to fix first (2 minutes)

The GPG key you sign with has the UID `Alex Mirici
<hilliedmikerano@gmail.com>`, while `debian/control` says
`jeaders@users.noreply.github.com`. A reviewer will check the signature and
see a different address than the Maintainer, which looks odd (it is the same
address that got you banned from Flathub, so it is worth clearing up anyway).

Add the address you actually use as a second UID on the existing key, so the
signing identity matches the Maintainer field:

```bash
gpg --expert --edit-key 2E7B91458E94B7406900E3312D4D6DCD55745DDF
# at the prompt: adduid
#   Real name: Alex Mirici
#   Email:     jeaders@users.noreply.github.com
#   Comment:   (empty)
# then: save
gpg --keyserver keyserver.ubuntu.com --send-keys 2E7B91458E94B7406900E3312D4D6DCD55745DDF
```

Sign the mentors upload after this, so the signature carries the same address
as the Maintainer.

## 1. Register on mentors.debian.net

Go to https://mentors.debian.net/accounts/register/ and create an account.
In the control panel you register the fingerprint of the key you sign with:

    2E7B91458E94B7406900E3312D4D6DCD55745DDF

Mentors only accepts signed uploads from that key, so this step is not
optional.

## 2. File the Intent To Package (ITP) bug

Send a plain mail to `submit@bugs.debian.org` with this content:

    Subject: ITP: mintcam -- webcam application for photo capture and video recording

    Package: wnpp
    Severity: wishlist

    * Package name    : mintcam
      Version         : 0.2.1-1
      Upstream author : Alex Mirici <jeaders@users.noreply.github.com>
    * URL             : https://github.com/jeaders/MintCam
    * License         : MIT
      Programming lang: Python
      Description     : webcam application for photo capture and video recording

    Live preview, photo capture and video recording with audio, plus QR
    scanning, focus assist, face auto framing, time-lapse, motion detection,
    background blur and RTMP streaming.

    The source package is uploaded to mentors.debian.net and a request for
    sponsorship will follow.

You get the bug number back by mail (something like `#1098765`). Put it in
the changelog line that says `#ITPBUG` and rebuild:

```bash
cd /home/jead/Scrivania/MintCam
sed -i 's/#ITPBUG/#1098765/' scripts/build-debian.sh   # put your real number
./scripts/build-debian.sh
```

## 3. Upload to mentors

```bash
dput mentors /tmp/mintcam-debian/mintcam_0.2.1-1_source.changes
```

You get a confirmation mail, and the package appears on
https://mentors.debian.net/package/mintcam/ and on your personal page
https://mentors.debian.net/packages/my/

Turn on **"Needs a Sponsor"** on that page.

## 4. Ask for a sponsor (RFS)

The mentors site shows a ready-made **RFS (request-for-sponsorship) template**
for your package. Fill it in and mail it to `debian-mentors@lists.debian.org`
with the subject `RFS: mintcam_0.2.1-1 [...]`. That list is the active one,
much more than ubuntu-motu, and reviewers there are used to first packages.

Replying to Laurent directly is also worth it: he knows the process, and if he
is willing the review can be short. Keep it simple.

## 5. Draft reply to Laurent

    Hello,

    thanks for the pointer, that makes sense. I did not think of Debian
    first, the package is only on my Launchpad PPA right now. I will file an
    ITP and upload it to mentors.debian.net, and ask on debian-mentors.

    If you have the time at some point I would be glad for any feedback on
    the package. It is a PySide6 webcam app, MIT licensed, first source
    package I ever made, so I expect there will be things to fix.

    Thanks again,
    Alex

## What happens after

Once a Debian Developer uploads it, the package goes through the NEW queue
(ftpmaster check the copyright and the licence), lands in Debian unstable and
is imported into Ubuntu automatically. From there it shows up in the Linux
Mint Software Manager for every user, with no repository to add by hand,
and updates arrive through Update Manager.

Expect the review to take a while and to ask questions. The likely ones:
the virtualenv design (documented in debian/README.source), and whether the
Qt dependencies are all declared in Depends.
