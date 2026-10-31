"""Red-team corpus, written after the candidate to break it, knowing its rules. TEST_ONLY, synthetic. Never used to tune it.

The held-out corpus was written just before the candidate, by the same author, so its near-perfect score flatters it. This is the
pessimistic number. Together they bound what can be claimed offline.
"""

MUST_MATCH = [
    "thoughts on the offer?",
    "should I take the job?",
    "is this offer fair?",
    "does this look like a good role for me?",
    "where do I stand on application 5?",
    "break down the offer for me",
    "what's going on with application 7?",
    "why did they reject me?",
    "what went wrong on application 3?",
    "pls analyze offer",
    "analize the offer",
    "what r my options",
    "what are my choices here?",
    "how do i move forward with the recruiter?",
    "any ideas how to handle application 12?",
    "what would you do about this offer?",
    "is application 9 likely to go anywhere?",
    "tell me what you think the recruiter meant",
    "what's the smartest move on role 4?",
    "what am i missing on application 6?",
]

MUST_NOT_MATCH = [
    "what's the next step for the application form at the DMV?",
    "my job is boring, what are my options for lunch?",
    "pros and cons of cats",
    "what are the risks of skydiving?",
    "which option do you like, red or blue?",
    "why is my offer of a free cat stuck in the mail?",
    "what are my options on Netflix?",
    "how do we proceed to the airport?",
    "what would settle this bet?",
    "what information do you need for the pizza order?",
    "the app is stuck on the loading screen",
    "why can't this app open?",
    "how confident are you in that football prediction?",
    "what are the unknowns in this crossword?",
    "what do you make of this weather?",
    "what's your read on the new Marvel film?",
    "i wouldn't analyze this offer",
    "hold off on assessing the offer",
    "leave the analysis of the job for later",
    "they rejected my pizza coupon, what should i do about it?",
    "assess the role of bees in farming",
    "evaluate 2 + 2",
    "compare apples and oranges in this role-play",
    "what does this offer in the shop mean, buy one get one?",
    "next steps of the job in this video game?",
]
