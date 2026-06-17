from __future__ import annotations

TEMPLATES: dict[str, list[str]] = {
    "trash_kda": [
        "{name}'s KDA is {kda}. At this point the enemy team should be sending them a thank-you card.",
        "A {kda} KDA? Bold strategy. Extremely ineffective, but bold.",
        "{name} is single-handedly funding the enemy team's night out.",
        "With a {kda} KDA, {name} isn't a teammate — they're a respawn timer.",
        "{name} has a {kda} KDA. The enemy team calls them 'free kills' in their VOD reviews.",
    ],
    "trash_hs": [
        "{hs}% headshot rate. {name} is basically a body-shot specialist. A very bad one.",
        "With {hs}% HS%, {name} is aiming for everything except the head.",
        "{name} shoots at faces and somehow hits kneecaps. {hs}% headshot rate speaks for itself.",
        "Reyna mains getting headshots at 30%+. {name} out here at {hs}% hitting shins.",
        "{hs}% HS% means {name} spends their bullets decorating walls.",
    ],
    "trash_winrate": [
        "{name} wins {wr}% of their games. The other {loss_wr}% are someone else's highlights.",
        "A {wr}% win rate. {name} isn't losing games — they're donating them.",
        "{name} has a {wr}% win rate. The enemy team's warmup routine.",
        "At {wr}% wins, {name} has lost more games than most people have played.",
        "{wr}% win rate. {name} is statistically the reason your friends won't duo with you.",
    ],
    "trash_acs": [
        "An ACS of {acs}. {name} was definitely in the server, just not doing much.",
        "{acs} average combat score. {name} is technically participating.",
        "{name} averages {acs} ACS. Even the spike plant gives more value.",
        "With {acs} ACS, {name} is less of a fragger and more of a scenic background character.",
        "{acs} ACS. {name} shows up, takes up space, and calls it a contribution.",
    ],
    "decent": [
        "{name} is perfectly average. Not bad enough to roast, not good enough to respect.",
        "{name}'s stats are the human equivalent of a shrug. {kda} KDA, {wr}% wins. Yep.",
        "A {kda} KDA and {wr}% win rate. {name} exists. That's about it.",
        "{name} is statistically mediocre. Which, honestly, takes consistency to maintain.",
        "Nothing to see here. {name} is aggressively average and somehow proud of it.",
    ],
    "good_performance": [
        "Okay, {name} actually cooked this time. {kda} KDA and {hs}% HS%. Respect... barely.",
        "{name} is playing well. {kda} KDA, {wr}% wins. Don't let it go to their head.",
        "Even a broken clock is right twice a day. {name} at {kda} KDA lately though — fair play.",
        "{name}'s been popping off. {kda} KDA, {acs} ACS. We hate to see it.",
        "The stats don't lie: {name} is actually performing. {wr}% wins, {kda} KDA. Disgusting.",
    ],
    "comparison_win": [
        "{name} won this comparison. Statistically better. Emotionally insufferable about it.",
        "{name} takes the W here. {kda} KDA vs the other guy's excuse for a stat card.",
        "The numbers have spoken. {name} is better. At least in Valorant.",
        "{name} edges this one out. Don't worry — the other person will recover. Probably.",
        "Clear winner: {name}. Sometimes the data is just not kind.",
    ],
    "comparison_loss": [
        "{name} lost this comparison. The stats are right there — hard to argue with them.",
        "Rough day for {name}. Got statistically bodied in the comparison.",
        "{name} came in second. Which is just first place for losers.",
        "The numbers have been consulted. {name} is not the winner today.",
        "{name} lost the comparison. The real loss was the KDA we made along the way.",
    ],
}
