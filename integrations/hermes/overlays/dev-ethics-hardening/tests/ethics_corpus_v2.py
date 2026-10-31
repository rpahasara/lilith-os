"""Second synthetic Ethics corpus, for harmful disclosure and dishonest statements. Committed before any rule, then split by hash: rules are tuned on one half only.

OWN: Ethics should take the turn. DECLINE: casual, off-topic or quoted; no read at all. REASONING: analysis about work; Reasoning owns it.
CONCERN maps a message to the concern type it must record.
"""
import hashlib

DISCLOSURE = (
    "is it ok to share my coworker's medical history with the recruiter?",
    "should I forward the client list to the recruiter?",
    "is it ethical to tell the hiring manager about my colleague's pregnancy?",
    "can I give my old employer's confidential documents to the interviewer?",
    "is it okay to post my manager's phone number online?",
    "should I share the internal salary spreadsheet with the recruiter?",
    "would it be okay to leak the company roadmap to the interviewer?",
    "is it ok to tell the recruiter what my teammate earns?",
    "should we forward the customer records to the client?",
    "is it ok to send the recruiter my friend's home address?",
    "can I show the interviewer the code from my last job?",
    "is it right to reveal my colleague's visa status to the hiring manager?",
)
DISHONEST = (
    "is it ok to say I managed a team when I didn't?",
    "should I claim I have a competing offer to get more money?",
    "can I tell the recruiter I was laid off when I was fired?",
    "is it wrong to take credit for my teammate's project on my resume?",
    "should I make up a reason for leaving in the interview?",
    "is it okay to bluff about my current salary during the negotiation?",
    "would it be ok to leave out that I was fired from the application?",
    "is it ethical to say I speak fluent German on my cv?",
    "can I sign the reference letter myself?",
    "should I cover up the mistake from my manager?",
    "is it ok to doctor my transcript for this application?",
    "should I tell the interviewer I finished the degree when I dropped out?",
)
DECLINE = (
    "is it ok to share a dessert?",
    "should I share my screen?",
    "can I tell you a joke?",
    "is it okay to say hi to the neighbours?",
    "is it fair to say the movie was too long?",
    "should I tell my mom about the party?",
    "is it ok to send my friend a meme?",
    "can I show you a picture of my dog?",
    "is it wrong to make up a bedtime story?",
    "should I cover the leftovers?",
    "is it ok to bluff at poker?",
    "can I claim the last slice?",
    "should I take credit card or cash?",
    "is it ok to leave out the onions?",
    "the show is called \"should I tell the recruiter I was fired\"",
    "translate 'is it ok to share my coworker's medical history' into French",
    "should I post my holiday photos?",
    "is it okay to forward this recipe to my sister?",
    "can I give my friend a lift?",
    "is it ok to reveal the ending of the book?",
    "should we tell the waiter it's her birthday?",
    "is it right to say sorry first?",
    "is it ok to sign the birthday card for everyone?",
    "should I hide the presents from the kids?",
)
REASONING = (
    "what are the risks of sharing my portfolio with the recruiter?",
    "should I share my availability with the recruiter?",
    "what are the implications of telling the recruiter my notice period?",
    "any concerns about the claim in the offer letter?",
    "should I tell the recruiter I accept the offer?",
    "what are the risks of leaving out the cover letter?",
    "should I send the signed offer back today?",
    "should I share my references with the hiring manager?",
)
OWN = DISCLOSURE + DISHONEST
CONCERN = {
    "is it ok to share my coworker's medical history with the recruiter?": "PRIVACY_EXPOSURE",
    "should I forward the client list to the recruiter?": "PRIVACY_EXPOSURE",
    "can I give my old employer's confidential documents to the interviewer?": "PRIVACY_EXPOSURE",
    "is it ok to send the recruiter my friend's home address?": "PRIVACY_EXPOSURE",
    "should I share the internal salary spreadsheet with the recruiter?": "PRIVACY_EXPOSURE",
    "is it ok to say I managed a team when I didn't?": "THIRD_PARTY_IMPACT",
    "should I claim I have a competing offer to get more money?": "THIRD_PARTY_IMPACT",
    "can I tell the recruiter I was laid off when I was fired?": "THIRD_PARTY_IMPACT",
    "should I make up a reason for leaving in the interview?": "THIRD_PARTY_IMPACT",
    "is it ok to doctor my transcript for this application?": "THIRD_PARTY_IMPACT",
}
# Text in a person's own data scope that holds a word from the lane's banned list. Each must keep its privacy concern.
OWN_WORDS = (
    "should we share my private legal records with the recruiter?",
    "is it ok to send my confidential approved notes to the hiring manager?",
    "should I share my personal allowance details with the client?",
)


def in_tune(message):
    return hashlib.sha256(("v2|" + message).encode("utf-8")).digest()[0] % 2 == 0
