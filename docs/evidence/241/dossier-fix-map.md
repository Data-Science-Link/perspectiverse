# Can a dossier fix this item? (Refs #237, PR #241)

## Headline

The before/after covers **all 20 planets and every face in the sample** (40 rows in `summary-sample.csv`). Score each row with the locked question in `summary-rubric.md`, word for word:

Does this text accurately say what these posts argue, with their specifics, in a way that tells a newcomer something useful?

Answer yes / no / unsure, per item, with the text and its top 8 posts. Do not drop a row. A label that does not match its top posts stays in this score.

## Secondary breakdown

The yes/no column below is a side note only. It does not change the headline and it does not remove an item from the replay.

A dossier rewrites `summary`, `brief`, and `detail` from the posts already on that planet or face. It does not rename the planet, retitle the face, or move posts. Where the column says no, the likely failure is the label or the cluster, so a dossier may not be what fixes it. The row is still scored.

Label-vs-top-posts mismatches are tracked in #290. From the first 26 rows, #290 names six items: `Business:Business-3`, `Environment:Environment-6`, `Culture:Culture-6`, `Culture:Culture-6:Culture-6A`, `Other:Other-9`, `Other:Other-15`. Those six stay in the headline. The two extra "no" rows in the table (Environment-6A, Other-15A) were appended after that score. They are this note's inference from the same posts, not a second finding, and they stay in the headline too.

## Sample

Edition 2026-10-20 (`data-snapshot` `b049731`). Seed 241.

The first 26 rows of `summary-sample.csv` are unchanged. They are 20 planets plus one face on each planet that already had two or more faces (6 faces).

Fourteen faces were appended, in planet-row order, for the planets that had no face row. The draw uses `Random(242)` (`seed + 1`, the same second stream as the original face picks) and only on those 14 planets, so the original six faces were not re-rolled. Each of the 14 has exactly one face, so the pick is index 0 of 1.

Planets with no face: **0** of 20.

The file is now 40 rows: 20 planets and 20 faces, one face each.

## Count

| | Items | Dossier can fix the text | Dossier cannot (label or cluster) |
|---|---:|---:|---:|
| Planets | 20 | 15 | 5 |
| Faces | 20 | 18 | 2 |
| Total | 40 | 33 | 7 |

This count is the secondary note, not the headline. The headline is 40 of 40. #290 names five of these planets plus face Culture-6A. This table still marks Culture-6A as text a dossier can rewrite, because the face title is "Movie praise". That does not take Culture-6A out of the headline, and #290 still owns the label mismatch. Environment-6A and Other-15A are marked no here because they share the planet's posts. They were not in #290's six.

## The five label misses

**Business-3, National Debt.** The top posts argue about a hospital bill of $500k ("how is that not a debt?"), whether providers use billing as leverage, and a write-down from $500k to $30k. One post says interest on the debt is larger than Social Security, Medicare, or the military. The name says national debt. The face **Business-3A, Debt Reality** can be rewritten to say what those posts argue. The planet name cannot.

**Environment-6, Animals.** The top posts are "for the blocked", "All for money", "For faeeee", "For the fires", "For your attention", "For Asylum", "FOR THE ANIMALS....", and "For the love of god". One line mentions animals. The cluster is the word "for". The face **Environment-6A** has the same title and the same posts.

**Culture-6, Street Fighter Movie.** The top post is about Nathan Fielder's "You Can See Everything". Others are the Cat in the Hat trailer, Wildwood, Day for Night, and Digger. Street Fighter is one post in that set. The face already in the sample, **Culture-6A, Movie praise**, is the general movie posts, and that title matches them, so a dossier can name those films. The planet name stays wrong.

**Other-9, Social Media Followers.** The posts are about followers: a rude follow, wanting more followers than one's hometown, thanks for 300 and for 1,000, an NSFW unfollow warning, and a giveaway at 150. The name is on that subject, unlike Animals or Street Fighter. The summary only says people are grateful. The blind baseline still called this a label miss, so the planet row is counted as no: a dossier can replace the gratitude sentence, and it cannot change the name that was rejected. The face **Other-9A, Gaining Followers** matches those posts, so its text can be rewritten.

**Other-15, College Football Playoff.** The posts are a cheer for an undefeated SEC team, one argument that the playoff excludes teams that do not outspend everyone, a rejection of going past 12 teams, and praise for a 24-team field. The summary keeps only the spending sentence. The face **Other-15A, Playoff Expansion** is the same mix, so the face title is one slice of the cluster.

## Every item

`yes` means the posts are about the labeled subject and the public text is thin, repetitive, filler, or missing the specifics. A briefing can say what those posts argue.

`no` means the label or the membership is the likely failure. A dossier would describe the posts it is given and would leave that failure in place. Either way the row stays in the headline score.

| Item | Kind | Dossier can fix it | Why |
|---|---|---|---|
| All topics:3 Trans Rights | planet | yes | Posts are about trans people. The summary is the filler sentence and copies the faces. |
| All topics:3:3B Trans Rights | face | yes | The face posts match the title. The text can be more specific and can stop repeating. |
| All topics:4 Musk Interference | planet | yes | Posts are about Musk, Ukraine, campaign money, and buying a senator. The text can carry those specifics. |
| All topics:4:4A Musk Accountability | face | yes | Same posts. The face title fits. Appended row. |
| Business:Business-3 National Debt | planet | no | Label does not match. Posts are a hospital bill, not the national debt. |
| Business:Business-3:Business-3A Debt Reality | face | yes | The face title is not "National Debt". A dossier can say the posts argue about a $500k hospital bill. Appended row. |
| Business:Business-8 Wealth Use | planet | yes | Posts are what people would do with vast wealth. |
| Business:Business-8:Business-8A Wealth Use | face | yes | Same posts, same title. Appended row. |
| Culture:Culture-6 Street Fighter Movie | planet | no | Label does not match. Top posts are several other movies. |
| Culture:Culture-6:Culture-6A Movie praise | face | yes | This face's posts are the general movie posts, and the title matches. |
| Culture:Culture-7 Twitter Fails | planet | yes | Posts are about Twitter. The text can name the claims. |
| Culture:Culture-7:Culture-7A Twitter Fails | face | yes | Same posts, same title. Appended row. |
| Education:Education-4 Book Bans | planet | yes | Posts are about banned books and access to knowledge. |
| Education:Education-4:Education-4A Book Bans | face | yes | Same posts, same title. Appended row. |
| Environment:Environment-6 Animals | planet | no | Label does not match. Posts are "for ..." fragments. |
| Environment:Environment-6:Environment-6A Animals | face | no | Same title, same posts. Appended row. |
| Environment:Environment-10 October Wind Advisory | planet | yes | Posts are wind advisories. The text can keep the speeds and the offices. |
| Environment:Environment-10:Environment-10A Winds Are High | face | yes | Same posts. The title fits. Appended row. |
| Health:Health-9 Therapy Effectiveness | planet | yes | Posts are about therapy. The summary is the filler sentence. |
| Health:Health-9:Health-9B Therapy Misused | face | yes | The face posts match misuse of therapy language. |
| Health:Health-1 US Healthcare System | planet | yes | Posts are about US healthcare, cost, and who it fails. |
| Health:Health-1:Health-1A Universal Healthcare | face | yes | Same posts. The title fits the claim in them. Appended row. |
| Other:Other-15 College Football Playoff | planet | no | Label does not match the mix (a cheer, spending, 12 teams, a 24-team field). |
| Other:Other-15:Other-15A Playoff Expansion | face | no | The title is one slice of that mix. Appended row. |
| Other:Other-3 Social Media Blocks | planet | yes | Posts are about blocks. The summary is the filler sentence. |
| Other:Other-3:Other-3B Social Media Blocks | face | yes | The face posts match the title. |
| Other:Other-9 Social Media Followers | planet | no | Recorded label miss. A dossier can replace "grateful", and it cannot change the name. |
| Other:Other-9:Other-9A Gaining Followers | face | yes | The posts are about gaining and having followers. Appended row. |
| Politics:Politics-3 MAGA Movement | planet | yes | Posts are about MAGA and voting. |
| Politics:Politics-3:Politics-3A MAGA Influence | face | yes | Same posts. The title fits. Appended row. |
| Sports:Sports-6 WNBA Finals | planet | yes | Posts are the WNBA Finals and the Valkyries. The summary is the filler sentence. |
| Sports:Sports-6:Sports-6A WNBA Finals | face | yes | The face posts match the title. |
| Sports:Sports-9 Jeremiah Smith Play | planet | yes | Posts are about Jeremiah Smith. |
| Sports:Sports-9:Sports-9A Jeremiah Smith | face | yes | Same posts, same subject. Appended row. |
| Technology:Technology-9 Data Centers | planet | yes | Posts are about data centers. The summary is the filler sentence. |
| Technology:Technology-9:Technology-9A Data Centers Harm | face | yes | The face posts match harm, petitions, and resource use. |
| Technology:Technology-7 AI Data Centres | planet | yes | Two of the three posts are the Nova Scotia petition and data-centre stocks. One is about AI in creative work. The name still fits the set well enough that the text is the lever. |
| Technology:Technology-7:Technology-7A AI Data Centres | face | yes | Same posts. Appended row. |
| World:World-4 Houthi Attacks | planet | yes | Posts are Houthi strikes on Saudi Arabia. |
| World:World-4:World-4A Houthi Attacks | face | yes | Same posts, same title. Appended row. |
