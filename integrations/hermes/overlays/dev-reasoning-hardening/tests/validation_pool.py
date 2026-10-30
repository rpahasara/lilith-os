"""Validation pool for the detector, committed before any new rule. TEST_ONLY, synthetic. Same author, but it is split by hash:

    in_tune(m) True   may be read and used while changing rules
    in_tune(m) False  never read during tuning; scored once, at the end, and its failures are reported, not fixed

Labels are fixed here. Editing one to make a result pass is not allowed.
"""

import hashlib

POSITIVE = [
    "any thoughts on the Lisbon offer?", "what's your take on the recruiter's silence?", "how do you see application 8 going?",
    "was it a mistake to turn down role 3?", "do you think they'll come back on application 44?", "what happened with my application to role 9?",
    "why was I rejected for job 17?", "why haven't they replied about application 12?", "why did the interview go badly?",
    "how am I doing on the job search?", "am I on track with application 5?", "where are we with the Oslo role?",
    "what's the status of my thinking on this offer, is it good?", "what would you advise on this offer?", "any advice on the salary negotiation?",
    "how should I respond to the recruiter?", "how do I handle the second interview?", "what's the best way to push application 2 forward?",
    "what would you do in my position on this job?", "should I chase the recruiter?", "should I withdraw application 6?",
    "is the offer any good?", "is this role a good fit?", "does the salary look reasonable?", "is this deadline realistic?",
    "does this rejection change anything?", "what am I overlooking on role 11?", "what did I miss in the cover letter?",
    "can you make sense of this feedback?", "help me understand the offer", "explain why application 20 stalled",
    "walk me through my options on the offer", "talk me through the risks of this role", "summarise where I stand on job 30",
    "pls assess the offer", "cn you analyze the feedback", "wat are my options on the role", "evalute this offer",
    "what are my alternatives to this offer?", "are there other paths for application 15?", "do I have any leverage on the salary?",
    "how likely is an offer from role 7?", "what are the chances on application 1?", "what's the upside of waiting on this job?",
    "what's the downside of accepting?", "which of the two offers should I take?", "is it better to accept now or wait for job 8?",
    "what's holding up application 26?", "what's the hold-up with the recruiter?", "who is blocking my offer?",
    "what do I need to do before the interview?", "what should my next move be on the application?", "where should I focus on the job search?",
    "does it make sense to follow up on application 33?", "is it too early to follow up on role 2?", "was the recruiter's reply a good sign?",
    "what does the silence from role 5 tell us?", "how should I read this email from the recruiter?", "what's really going on with this offer?",
    "tell me honestly, is application 41 dead?",
]

NEGATIVE = [
    "any thoughts on the new Bond film?", "what's your take on pineapple pizza?", "how do you see the match going?",
    "was it a mistake to dye my hair?", "do you think it'll rain?", "what happened in the last episode?",
    "why was the train late?", "why haven't the plants grown?", "why did the cake sink?",
    "how am I doing on this crossword?", "am I on the right bus?", "where are we on the map?",
    "what would you advise for a sore throat?", "any advice on growing tomatoes?", "how should I cook rice?",
    "how do I handle a noisy neighbour?", "what's the best way to boil an egg?", "what would you do on a desert island?",
    "should I chase the cat?", "should I get a haircut?", "is the soup any good?", "is this shirt a good fit?",
    "does this paint look reasonable?", "is this recipe realistic?", "what am I overlooking in this sudoku?",
    "help me understand photosynthesis", "explain why the sky is blue", "talk me through this card trick",
    "walk me through setting up my router", "are there other paths up the mountain?", "how likely is snow tomorrow?",
    "what are the chances of rain?", "what's the upside of cold showers?", "which of the two sofas should I take?",
    "is it better to walk or cycle?", "what's holding up the shelf?", "who is blocking the driveway?",
    "what do I need to do before the holiday?", "does it make sense to buy a kettle?", "what's really going on in this show?",
    "the game has a job system, what are my options there?", "in the play she has the role of a nurse",
    "the actor got a role in a new film", "i got an offer on my old bike", "there's a job lot of chairs for sale",
    "my application of sunscreen was uneven", "the app crashed again",
    "don't give me your thoughts on the offer", "i don't need advice on application 4", "no thoughts on the recruiter please",
    "skip the advice about role 8", "please don't tell me what to do about the offer", "not interested in your take on job 3",
    'she asked "should I take the job?" in the film', 'the headline read "is this offer fair?"', "quote: what's your take on the offer",
    "translate 'should I accept the offer' to Spanish", "write a song about a job interview", "summarise the plot of The Interview",
    "good night", "cheers mate", "haha nice one",
]


def in_tune(message):
    return hashlib.sha256(message.encode("utf-8")).digest()[0] % 2 == 0
