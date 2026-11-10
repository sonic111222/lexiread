# Launch notes

This is a free, non-commercial, source-available project. The code is public,
but commercial use requires a separate written license. The goal of the first
month is not revenue; it is finding real users and turning their feedback into
a better reading workflow.

## Before the first public link

- [ ] Choose the final brand name and check for obvious trademark conflicts.
- [ ] Verify README/README_EN point to the real GitHub repository path.
- [ ] Upload `docs/social-preview.png` in GitHub repository Settings → Social preview.
- [ ] Set the repository About: “Local-first English reading studio: Windows OCR, offline dictionary, optional AI.”
- [ ] Add topics: `english-learning`, `ocr`, `windows`, `flask`, `education`, `ai`, `reading`.
- [ ] Pin the repository on the maintainer profile.
- [ ] Build and test the Windows release zip.
- [ ] Make sure no `data/lexiread.db`, API key or private upload is committed.
- [ ] Prepare a 30-second screen recording and 3–5 screenshots.
- [ ] Reply-to-comments plan: for the first hour after each post.

## GitHub launch

1. Publish `v0.1.0` with a portable Windows zip and SHA256.
2. Add a short “Why I built this” section to the README or a discussion post.
3. Share with:
   - HelloGitHub
   - GitHubDaily
   - V2EX
   - 少数派 / 小众软件 (submit the project, do not spam)
   - relevant English-learning and source-available/open-source communities
4. Ask for specific feedback:
   - “Which question type breaks the parser?”
   - “What would make the word panel more useful?”
   - “Would you use a phone-camera → desktop workflow?”

Avoid asking for stars directly; ask for a test and a concrete bug.

## Xiaohongshu: first five notes

The account should feel like a person documenting a useful learning workflow,
not a software ad.

### 1. The transformation

Title idea: 《我把一张六级阅读截图，变成了可以点词的精读页》

Cover: left side original screenshot, right side clean reading page; large
title “一张题图 → 精读课”.

Carousel:
1. The problem: reading with a dictionary in another window.
2. Upload + OCR review.
3. Reading page.
4. Point at a word: Chinese meaning + source sentence.
5. Add to wordbook.
6. “免费非商业使用，源码公开，Windows，本地 OCR；需要试用可以留言你在练什么题。”

### 2. The method

Title idea: 《英语精读最容易忽略的一步：把词放回原句》

Content: explain why an isolated definition is not enough; show how the same
word changes meaning in context. Use the app screenshots as illustrations, not
as a product catalogue.

### 3. The build story

Title idea: 《为什么我做了一个图片不上传的英语精读工具》

Content: local-first privacy, OCR limitations, why the wordbook is a local
SQLite file, what the app deliberately does not do. Invite people to test on
Windows. This note targets the indie-maker / source-available audience.

### 4. The workflow

Title idea: 《考研阅读复盘：先做题，再对依据，最后只收藏真正不会的词》

Content: a three-step study routine; show the answer evidence panel and the
review cards. Emphasize the method, not “AI gives answers”.

### 5. The invitation

Title idea: 《公开了一个英语精读工具的源码，想找 20 个 Windows 用户帮我挑错》

Content: state clearly that it is free for personal/noncommercial use, the
source is public, and it is early. Ask for:
Windows version, OCR language pack, test type, and one bug. Do not post
QR codes or direct external links in every note.

## Metrics to watch

- GitHub: clones/downloads, issues with reproduction details, contributors,
  release downloads, stars (vanity only).
- Xiaohongshu: saves, comments asking a real study question, profile visits,
  follow-up conversations.
- Product: first upload → OCR review → reading completion → word saved.
- Quality: OCR error rate on your test images; AI answer/evidence agreement on a
  small manually checked set.

## Do not do

- Buy stars, comments or downloads.
- Claim “提分”, “保过”, “押题”, or “最有效”.
- Post full copyrighted exam papers, textbook scans, or other people’s
  screenshots without permission.
- Put API keys, personal data or unblurred names in screenshots.
- Make a note look like an ad if it is not disclosed as an ad.
- Spam the same link into study groups.
