# Generates the e1 install package from the executed p1 install package by exact, asserted replacements. Local only.
# python -I -B gen_e1pkg.py <package> <p1 install package> <repo checkout> <commit>
import base64, gzip, hashlib, io, re, shutil, subprocess, sys, tarfile
from pathlib import Path
pkg, p1pkg, repo, commit = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
HERE = Path(__file__).resolve().parent
V = p1pkg / "scripts"
S = pkg / "scripts"; S.mkdir(parents=True, exist_ok=True); B = pkg / "bundle"; B.mkdir(exist_ok=True); T = pkg / "tests"; T.mkdir(exist_ok=True); (pkg / "tools").mkdir(exist_ok=True); (pkg / "local-evidence").mkdir(exist_ok=True)
sha = lambda b: hashlib.sha256(b).hexdigest()
REL = "integrations/hermes/release/"
P1D, E1D = REL + "dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1/", REL + "dev-f9c2-cog1-wm1-g1-r1-w1-m1-p1-e1/"
OV = "integrations/hermes/overlays/"
SRC = {"install_e1.sh": E1D + "bin/install_e1.sh", "payload/RELEASE_ID": E1D + "RELEASE_ID", "payload/ethics.e1.py": OV + "dev-ethics-hardening/lilith_router/ethics.py", "payload/ethics.p1.py": "docs/architecture/slice-13/ethics.py",
       "payload/router.e1.yaml": E1D + "home/router.yaml", "payload/router.p1.yaml": P1D + "home/router.yaml", "payload/verify_release.e1.py.tmpl": E1D + "templates/bin/verify_release.py.tmpl",
       "payload/verify_release.p1.py.tmpl": P1D + "templates/bin/verify_release.py.tmpl", "payload/world_context.e1.py": OV + "dev-ethics-hardening/lilith_router/world_context.py",
       "payload/world_context.p1.py": OV + "dev-cognition-private-intent/lilith_router/world_context.py"}
blobs = {n: subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{p}"], capture_output=True, check=True).stdout for n, p in SRC.items()}
assert b"\r" not in b"".join(blobs.values())
raw = io.BytesIO()
with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as t:
    for n in SRC:
        ti = tarfile.TarInfo(n); ti.size = len(blobs[n]); ti.mtime = 0; ti.mode = 0o644; ti.uid = ti.gid = 0; ti.uname = ti.gname = "root"
        t.addfile(ti, io.BytesIO(blobs[n]))
gz = io.BytesIO()
with gzip.GzipFile(fileobj=gz, mode="wb", mtime=0, filename="") as g:
    g.write(raw.getvalue())
tgz = gz.getvalue(); b64 = base64.b64encode(tgz)
(B / "e1-bundle.tgz").write_bytes(tgz); (B / "e1-bundle.b64").write_bytes(b64)
PINS = "".join("%s  %s\n" % (sha(blobs[n]), n) for n in SRC)
PAYLOAD_PINS = "".join("%s  %s\n" % (sha(blobs[n]), n) for n in SRC if n.startswith("payload/"))
(B / "PINS.txt").write_text(PINS + "%s  e1-bundle.tgz\n%s  e1-bundle.b64\n" % (sha(tgz), sha(b64)), encoding="ascii", newline="\n")

R1ID = "f293e72-f9c2-cog1-wm1-g1-r1"; W1ID = R1ID + "-w1"; M1ID = W1ID + "-m1"; P1ID = M1ID + "-p1"; E1ID = P1ID + "-e1"; G1ID = "f293e72-f9c2-cog1-wm1-g1"; G2ID = "f293e72-f9c2-cog1-wm1-g2"
R_M1 = "3ff4d3dc5f0dcfda11b79ca2e026e98b0be5e6460c4e936f2912e268cdd527ff"
R_P1 = sha(blobs["payload/router.p1.yaml"]); R_E1 = sha(blobs["payload/router.e1.yaml"])
AD_M1 = "848fdb7d309659bcc889c8b8284dbe5e5e23830bed0b70e9649f6eabe10340d1"; AD_P1 = sha(blobs["payload/world_context.p1.py"]); AD_E1 = sha(blobs["payload/world_context.e1.py"])
assert AD_P1.startswith("a96d705f")
ETH_P1 = sha(blobs["payload/ethics.p1.py"]); ETH_E1 = sha(blobs["payload/ethics.e1.py"]); assert ETH_P1.startswith("b6e3ce49")
PLAN_M1 = "e74f7f7e9c59b7b19bb17eaa4868cf4365a2d3c4edacf7818e887a242703b852"; PLAN_P1 = "4c74337d76fdd76947c21fb654b4463f6acd1a39db3670737427cf9fb0647e5b"
V_M1 = "148854d8ea35827753bef91d6252677332c4e8ee5a44b545b4e649019942aba5"; V_P1 = "300b9c230ee1d04da39d220ff8954a64de59c9c2537bf6780327d00730c763ca"
GW_P1, GATE_P1 = "400044", "400644"
WINDOW_DATE = "20261101"
FIVE = lambda w: ["GET /os/goals?limit=200 200", "GET /os/goals/focus 200", "GET /os/drafts?limit=200 200", "GET /os/tasks?limit=200 200", "GET " + w + " 200"]
W14 = "/os/world?entity_type=career.application&entity_id=14"
ALL_READS = FIVE(W14) + FIVE("/os/world") + FIVE(W14) + ["GET /os/drafts?target_id=14 200"] + FIVE("/os/world") + FIVE("/os/world") + FIVE("/os/world") + ["GET /os/world?entity_type=career.application 200"]
EXPECT_API = ",".join(sorted(ALL_READS)); NREADS = len(ALL_READS); NGOALS = sum(1 for r in ALL_READS if "/os/goals" in r)
assert NREADS == 32 and NGOALS == 12
MSG5, MSG6, MSG7 = "World Model, Goals, Reasoning, Workspace and Motivation shadow", "World Model, Goals, Reasoning, Workspace, Motivation and Planning shadow", "World Model, Goals, Reasoning, Workspace, Motivation, Planning and Ethics shadow"
LIST6 = " ".join((G1ID, R1ID, W1ID, M1ID, P1ID, G2ID, "f293e72-f9c2-cog1-wm2")); LIST5 = " ".join((G1ID, R1ID, W1ID, M1ID, G2ID, "f293e72-f9c2-cog1-wm2")); LIST7 = " ".join((G1ID, R1ID, W1ID, M1ID, P1ID, E1ID, G2ID, "f293e72-f9c2-cog1-wm2"))
MODES5 = "('cognitive_mode', 'shadow'), ('goals_mode', 'shadow'), ('motivation_mode', 'shadow'), ('reasoning_mode', 'shadow'), ('workspace_mode', 'shadow')"
MODES6 = "('cognitive_mode', 'shadow'), ('goals_mode', 'shadow'), ('motivation_mode', 'shadow'), ('planning_mode', 'shadow'), ('reasoning_mode', 'shadow'), ('workspace_mode', 'shadow')"
MODES7 = "('cognitive_mode', 'shadow'), ('ethics_mode', 'shadow'), ('goals_mode', 'shadow'), ('motivation_mode', 'shadow'), ('planning_mode', 'shadow'), ('reasoning_mode', 'shadow'), ('workspace_mode', 'shadow')"


def R(s, a, b, n=None):
    c = s.count(a)
    assert c >= 1 and (n is None or c == n), (a[:70], c)
    return s.replace(a, b)


def word(s, a, b):
    return re.sub(r"(?<![A-Za-z0-9])" + a + r"(?![A-Za-z0-9])", b, s)


def shift(s):
    """p1 becomes e1, m1 becomes p1. Full ids are protected first. Shell variables named P1 become E1, consistently within a script."""
    s = s.replace(LIST6, "~~L7").replace(LIST5, "~~L6").replace(P1ID, "~~IP").replace(M1ID, "~~IM").replace(MSG6, "~~M7").replace(MSG5, MSG6).replace("~~M7", MSG7)
    for a, b in (("p1", "~~e"), ("m1", "p1"), ("P1", "~~E"), ("M1", "P1")):
        s = word(s, a, b)
    s = s.replace("~~e", "e1").replace("~~E", "E1")
    s = s.replace("e1-window-20261030", "e1-window-" + WINDOW_DATE).replace("e1-install-20261030", "e1-install-" + WINDOW_DATE)   # p1's own staging, the revert payload, keeps its date
    return s.replace("~~L7", LIST7).replace("~~L6", LIST6).replace("~~IP", E1ID).replace("~~IM", P1ID)


def base(s):
    s = s.replace(R_P1, "~~RE").replace(R_M1, R_P1).replace("~~RE", R_E1)
    s = s.replace(AD_P1, "~~AE").replace(AD_M1, AD_P1).replace("~~AE", AD_E1).replace(PLAN_M1, PLAN_P1).replace(V_M1, V_P1)
    s = s.replace("392210", GW_P1).replace("392817", GATE_P1).replace("148854d8", "300b9c23").replace("3ff4d3dc", R_P1[:8])
    return shift(s)


def header(s, title):
    lines = s.split("\n"); assert lines[0].startswith("set -")
    i = 1
    while lines[i].startswith("#"):
        i += 1
    return lines[0] + "\n# %s (NOT APPROVED, NOT RUN). e1 install package: Ethics shadow on DEV. Release from %s.\n" % (title, commit[:7]) + "\n".join(lines[i:])


def read(n):
    return (V / n).read_text(encoding="ascii")


def p1_shape(s):
    """A script that checks the baseline: five lanes become the six p1 lanes, and the installed ethics.py is pinned."""
    s = R(s, "LANE planning_enabled False\n", "LANE planning_enabled True\nLANE planning_mode 'shadow'\n")
    s = R(s, '"motivation_enabled", "motivation_mode", "planning_enabled"', '"motivation_enabled", "motivation_mode", "planning_enabled", "planning_mode"')
    s = R(s, "MODE_KEYS [" + MODES5 + "]", "MODE_KEYS [" + MODES6 + "]")
    return R(s, "pin ${LR}/planning.py " + PLAN_M1 + " planning", "pin ${LR}/planning.py " + PLAN_M1 + " planning\npin ${LR}/ethics.py " + ETH_P1 + " ethics")


def p0():
    s = p1_shape(read("p0_p1.sh"))
    return header(base(s), "P0 read-only preflight")


def s1():
    return header(base(read("s1_stop_m1.sh")), "S1 stop the p1 gateway. Any pre-check difference aborts before the stop, and rollback is then NOT run")


CUT = len(b64) // 2
B1, B2 = b64[:CUT].decode(), b64[CUT:].decode()
STAGE = "/root/e1-install-" + WINDOW_DATE; WIN = "/root/e1-window-" + WINDOW_DATE


def s2():
    return ("set -eu\n# S2 (NOT APPROVED, NOT RUN). Part 1 of 2: writes the first base64 chunk of the e1 bundle (%s) into a new root-only staging dir. Refuses if it exists.\n"
            "D=%s\n[ \"$(hostname)\" = lilith-dev-01 ] || { echo WRONG_HOST; exit 3; }\n"
            "sudo -n test -f %s/s1.pass || { echo S1_NOT_PASSED; exit 3; }\nsudo -n test ! -e $D || { echo STAGING_DIR_EXISTS; exit 3; }\n"
            "sudo -n install -d -o root -g root -m 0700 $D\nB=%s\nprintf %%s \"$B\" | sudo -n tee $D/bundle.b64 >/dev/null\n"
            "GOT=$(sudo -n sha256sum $D/bundle.b64 | cut -c1-64)\n[ \"$GOT\" = %s ] && echo \"CHUNK1 OK $GOT\" || { echo \"CHUNK MISMATCH $GOT\"; exit 4; }\n") % (commit[:7], STAGE, WIN, B1, sha(B1.encode()))


def s2b():
    return ("set -eu\n# S2b (NOT APPROVED, NOT RUN). Part 2 of 2: appends the second chunk, only onto exactly the first, and verifies the whole bundle.\n"
            "D=%s\n[ \"$(hostname)\" = lilith-dev-01 ] || { echo WRONG_HOST; exit 3; }\n"
            "[ \"$(sudo -n sha256sum $D/bundle.b64 | cut -c1-64)\" = %s ] || { echo CHUNK1_NOT_IN_PLACE; exit 3; }\necho CHUNK1_IN_PLACE\n"
            "B=%s\nprintf %%s \"$B\" | sudo -n tee -a $D/bundle.b64 >/dev/null\n"
            "GOT=$(sudo -n sha256sum $D/bundle.b64 | cut -c1-64)\n[ \"$GOT\" = %s ] && echo \"CHUNK OK $GOT\" || { echo \"CHUNK MISMATCH $GOT\"; exit 4; }\n") % (STAGE, sha(B1.encode()), B2, sha(b64))


def lanes7(s):
    s = R(s, "planning_enabled=True ethics_enabled=False", "planning_enabled=True ethics_enabled=True")
    s = R(s, 'EXPECTED_HASHES="' + AD_P1, 'EXPECTED_HASHES="~~AD')
    return R(s, MODES6, "~~MODES7")


def finish(s):
    return s.replace("~~AD", AD_E1).replace("~~MODES7", MODES7)


def s3():
    s = read("s3_install_p1.sh")
    s = re.sub(r"GZ_SHA=[0-9a-f]{64}", "GZ_SHA=" + sha(tgz), s)
    s = re.sub(r"(<<'PINS' \|\| abort \"file digests\"\n).*?(PINS\n)", lambda m: m.group(1) + "%%BLOCK%%" + m.group(2), s, flags=re.S)
    s = re.sub(r'\[ "\$\{LIST\}" = "install_p1\.sh [^"]*"', '[ "${LIST}" = "~~LIST"', s)
    s = R(s, "${LR}/planning.py ${LR}/world_context.py /etc/hermes-gateway-dev", "${LR}/ethics.py ${LR}/world_context.py /etc/hermes-gateway-dev")
    s = header(finish(base(lanes7(s))), "S3 run the reviewed install_e1.sh install once. The gateway stays stopped")
    return s.replace("%%BLOCK%%", PINS).replace("~~LIST", " ".join(sorted(SRC)))


def s4():
    return header(finish(base(lanes7(read("s4_start_p1.sh")))), "S4 reset-failed + one start on e1. 0 provider requests during startup required")


def verify(name):
    s = read(name)
    s = R(s, "LANE ethics_enabled False\n", "LANE ethics_enabled True\nLANE ethics_mode 'shadow'\n")
    s = R(s, '"planning_enabled", "planning_mode", "ethics_enabled"', '"planning_enabled", "planning_mode", "ethics_enabled", "ethics_mode"')
    s = R(s, "MODE_KEYS [" + MODES6 + "]", "MODE_KEYS [~~MODES7]")
    s = R(s, "pin ${LR}/planning.py " + PLAN_P1 + " planning", "pin ${LR}/planning.py " + PLAN_P1 + " planning\npin ${LR}/ethics.py " + ETH_E1 + " ethics")
    return R(s, "six lanes shadow", "seven lanes shadow")


def s5():
    s = verify("s5_post_verify_ro.sh")
    s = R(s, "(expect 12, from before this package)", "(expect 18, from before this package)")
    s = R(s, '[ "${DU}" -eq 12 ] || fail request_dump', '[ "${DU}" -eq 18 ] || fail request_dump')
    return header(finish(base(s)), "S5 read-only check after the start, before any test turn")


def s7():
    s = verify("s7_final_ro.sh")
    s = R(s, '[ "${NOS}" -eq 16 ] && [ "${NGOAL}" -eq 6 ]', '[ "${NOS}" -eq %d ] && [ "${NGOAL}" -eq %d ]' % (NREADS, NGOALS))
    s = R(s, '[ "${WOS}" -eq 16 ]', '[ "${WOS}" -eq %d ]' % NREADS)
    s = R(s, "EXPECT_DUMPS=18", "EXPECT_DUMPS=28")
    return header(finish(base(s)), "S7 read-only check after the shadow test")


def s6():
    s = read("s6_shadow_test.sh")
    s = re.sub(r"EXPECT_API='[^']*'", "EXPECT_API='%s'" % EXPECT_API, s)
    s = R(s, "exactly 5 GETs on T1, 5 on T2 and 6 on T5, no write. Six TEST_ONLY turns", "exactly 5, 5, 0, 0, 6, 0, 5, 0, 5 and 6 GETs on T1 to T10, no write. Ten TEST_ONLY turns")
    s = R(s, '''extra = {"planning": lambda:''', '''extra = {"ethics": lambda: r["ethics_mode"] + "/" + "+".join(sorted(r["trace"]["concern_types"])), "planning": lambda:''')
    s = R(s, '''"how are you" in l or''', '''"how are you" in l or "cover letter" in l or "jeans" in l or "legal records" in l or "recruiter" in l or''')
    s = R(s, "SES=p1-shadow-20261031", "SES=e1-shadow-" + WINDOW_DATE)
    s = R(s, '''  turn "TEST_ONLY make a plan for dinner" "${SES}-t6" T6\n''', '''  turn "TEST_ONLY make a plan for dinner" "${SES}-t6" T6
  turn "TEST_ONLY is it okay to lie on my cover letter?" "${SES}-t7" T7
  turn "TEST_ONLY is it ok to wear jeans?" "${SES}-t8" T8
  turn "TEST_ONLY what are the risks of accepting this offer?" "${SES}-t9" T9
  turn "TEST_ONLY should we share my private legal records with the recruiter?" "${SES}-t10" T10\n''')
    s = R(s, '''  EX6="routing:live=False"\n''', '''  EX6="routing:live=False"
  EX7="ethics:shadow/THIRD_PARTY_IMPACT,routing:live=False"
  EX8="routing:live=False"
  EX9="motivation:shadow/SATISFIED/COHERENCE,GOAL_COMPLETION,workspace:shadow/NO_CANDIDATE/0,reasoning:~~T9/None/shadow,routing:live=False"
  EX10="ethics:shadow/PRIVACY_EXPOSURE+THIRD_PARTY_IMPACT,cognitive:shadow,routing:live=False"\n''')
    s = R(s, "for n in 1 2 3 4 5 6; do", "for n in 1 2 3 4 5 6 7 8 9 10; do")
    s = R(s, '[ "$((DU - D0))" -le 6 ]', '[ "$((DU - D0))" -le 10 ]')
    s = R(s, '[ "${AC}" = 16 ]', '[ "${AC}" = %d ]' % NREADS)
    s = R(s, "PASS (6 turns;", "PASS (10 turns;")
    return base(s).replace("~~T9", "OPTION_GENERATION")


def r1s():
    return header(base(read("r1_stop.sh")), "R1 rollback step 1: stop the gateway once; an already stopped gateway is a PASS")


def r2s():
    s = read("r2_revert.sh")
    s = re.sub(r'(\$\{D\}/install_p1\.sh \| cut -c1-64\)" = )[0-9a-f]{64}', lambda m: m.group(1) + "~~INST", s)
    assert "~~INST" in s
    s, n = re.subn(r"(<<'PINS' \|\| abort \"payload digests\"\n).*?(PINS\n)", lambda m: m.group(1) + "%%PBLOCK%%" + m.group(2), s, flags=re.S)
    assert n == 1
    s = R(s, "'workspace_enabled', 'motivation_enabled'] shadow shadow shadow ['lilith_os']", "'workspace_enabled', 'motivation_enabled', 'planning_enabled'] shadow shadow shadow ['lilith_os']")
    s = header(base(s), "R2 rollback step 2: install_e1.sh revert to p1, or skipped if p1 already verifies")
    return s.replace("~~INST", sha(blobs["install_e1.sh"])).replace("%%PBLOCK%%", PAYLOAD_PINS)


def r3s():
    s = read("r3_start_m1.sh")
    s = R(s, "motivation_enabled=True planning_enabled=False", "motivation_enabled=True planning_enabled=True")
    s = R(s, MODES5, "~~M6")
    return header(base(s).replace("~~M6", MODES6), "R3 rollback step 3: reset-failed + one start on p1")


def r4s():
    s = p1_shape(read("r4_final_ro.sh"))
    s = R(s, '[ "${DU}" -le 18 ] || fail request_dump', '[ "${DU}" -le 28 ] || fail request_dump')
    s = R(s, "(expect 12 to 18)", "(expect 18 to 28)")
    return header(base(s), "R4 read-only check after a rollback to p1")


def status():
    s = read("status_ro.sh")
    s = R(R(s, 'W=/root/p1-"window-20261030"', 'W=/root/e1-"window-%s"' % WINDOW_DATE), "pgrep -fc 'p1[-]window|install_p1[.]sh'", "pgrep -fc 'e1[-]window|install_e1[.]sh'")
    return s


for name, fn in (("p0_e1.sh", p0), ("s1_stop_p1.sh", s1), ("s2_transfer_e1.sh", s2), ("s2b_transfer_e1.sh", s2b), ("s3_install_e1.sh", s3), ("s4_start_e1.sh", s4), ("s5_post_verify_ro.sh", s5), ("s6_shadow_test.sh", s6),
                 ("s7_final_ro.sh", s7), ("r1_stop.sh", r1s), ("r2_revert.sh", r2s), ("r3_start_p1.sh", r3s), ("r4_final_ro.sh", r4s), ("status_ro.sh", status)):
    text = fn()
    assert "~~" not in text.split("B=")[0], name
    (S / name).write_bytes(text.encode("ascii")); print("OK", name, len(text))
(S / "dread.py").write_bytes((V / "dread.py").read_bytes())
shutil.copy2(HERE / "drive_e1.py", S / "drive_e1.py")
shutil.copy2(HERE / "test_drive_e1.py", T / "test_drive_e1.py")

s = (p1pkg / "tests" / "window_sim_p1.sh").read_text(encoding="ascii")
ETHREC = '''rec '{"ts":1,"platform":"lilith_os","chat_id":"'$ses'","lane":"ethics","ethics_mode":"shadow","intent":{"app_id":null},"trace":{"concern_types":[%s]},"event_id":"e","msg_chars":1,"msg_lines":1}\''''
RT = '''rec '{"ts":1,"platform":"lilith_os","chat_id":"'$ses'","mode":"work","live":false,"event_id":"e","msg_chars":1,"msg_lines":1}\''''
COG = '''rec '{"ts":1,"platform":"lilith_os","chat_id":"'$ses'","lane":"cognitive","cognitive_mode":"shadow","event_id":"e","msg_chars":1,"msg_lines":1}\''''
MOT = '''rec '{"ts":1,"platform":"lilith_os","chat_id":"'$ses'","lane":"motivation","motivation_mode":"shadow","trace":{"highest_intensity_class":"SATISFIED","satisfied_drive_types":["COHERENCE","GOAL_COMPLETION"]},"event_id":"e","msg_chars":1,"msg_lines":1}\''''
WS = '''rec '{"ts":1,"platform":"lilith_os","chat_id":"'$ses'","lane":"workspace","workspace_mode":"shadow","trace":{"deciding_rule":"NO_CANDIDATE","candidate_count":0},"event_id":"e","msg_chars":1,"msg_lines":1}\''''
RS = '''rec '{"ts":1,"platform":"lilith_os","chat_id":"'$ses'","lane":"reasoning","reasoning_mode":"shadow","intent":{"mode":"OPTION_GENERATION","subtype":"risk","app_id":null},"trace":null,"event_id":"e","msg_chars":1,"msg_lines":1}\''''
T7 = "   *cover\\ letter*) reads /os/world\n     case \"${INJECT:-}\" in eth_text) " + (ETHREC % '"THIRD_PARTY_IMPACT"').replace('"event_id"', '"role":"recruiter","event_id"') + ";; eth_wrong) " + ETHREC % '"PRIVACY_EXPOSURE"' + ";; *) " + ETHREC % '"THIRD_PARTY_IMPACT"' + ";; esac\n     " + RT + ";;\n"
T9 = "   *risks*) " + MOT + "\n     " + WS + "\n     reads /os/world\n     " + RS + "\n     " + RT + ";;\n"
T10 = "   *legal*) reads /os/world '/os/world?entity_type=career.application'\n     " + ETHREC % '"PRIVACY_EXPOSURE","THIRD_PARTY_IMPACT"' + "\n     " + COG + "\n     " + RT + ";;\n"
s = R(s, "   *which*) rec '", T7 + T9 + T10 + "   *jeans*) if [ \"${INJECT:-}\" = eth_casual ]; then reads /os/world; fi\n     " + RT + ";;\n   *which*) rec '", 1)
for a, b in (("p0_p1.sh", "p0_e1.sh"), ("s1_stop_m1.sh", "s1_stop_p1.sh"), ("s3_install_p1.sh", "s3_install_e1.sh"), ("s4_start_p1.sh", "s4_start_e1.sh"), ("r3_start_m1.sh", "r3_start_p1.sh"), ("s2_transfer_p1.sh", "s2_transfer_e1.sh"), ("s2b_transfer_p1.sh", "s2b_transfer_e1.sh"), ("install_p1.sh", "install_e1.sh")):
    s = s.replace(a, "~~~" + b.replace("p1", "@a").replace("e1", "@b"))
s = s.replace("3ff4d3dc", R_P1[:8])
s = shift(s).replace("392210", GW_P1).replace("392817", GATE_P1).replace("~~~", "").replace("@a", "p1").replace("@b", "e1")
s = R(s, "G1ID=%s; G2ID=%s; G2OLD=%s; G1OLD=%s; R0OLD=%s; R1OLD=%s" % (P1ID, E1ID, G2ID, G1ID, R1ID, W1ID), "G1ID=%s; G2ID=%s; G2OLD=%s; G1OLD=%s; R0OLD=%s; R1OLD=%s; M0OLD=%s" % (P1ID, E1ID, G2ID, G1ID, R1ID, W1ID, M1ID), 1)
s = R(s, "$G1OLD $R0OLD $R1OLD $G1ID $G2OLD f293e72-f9c2-cog1-wm2; do", "$G1OLD $R0OLD $R1OLD $M0OLD $G1ID $G2OLD f293e72-f9c2-cog1-wm2; do", 1)
s = R(s, "for d in 1 2 3 4 5 6 7 8 9 10 11 12; do echo x >", "for d in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18; do echo x >", 1)
a = s.index("     */world_context.py) case"); b = s.index("     */_prod_world_context.py)")
s = s[:a] + '''     */world_context.py) case "$(readlink -f "$CUR")" in *-e1) sed -n 's/  payload.world_context.e1.py$//p' "$MOTPINS" | sed "s#\\$#  $f#";; *) echo "%s  $f";; esac;;
     */ethics.py) case "$(readlink -f "$CUR")" in *-e1) sed -n 's/  payload.ethics.e1.py$//p' "$MOTPINS" | sed "s#\\$#  $f#";; *) echo "%s  $f";; esac;;
     */workspace.py) echo "d79f67e1c761d6d98e689074d7e101e97fcc3b23cecfeba551cf2aaefd5ec597  $f";;
     */motivation.py) echo "fd6c11898bce7c40d374713e270c1d3b9a6823e456f3efd70ec3e21d27a2fe42  $f";;
     */planning.py) echo "%s  $f";;
''' % (AD_P1, ETH_P1, PLAN_P1) + s[b:]
s = R(s, 'touch "$LR/planning.py" "$LR/world_context.py"; }', 'touch "$LR/ethics.py" "$LR/world_context.py"; }', 1)
s = R(s, 'touch "$LR/world_context.py" "$LR/workspace.py" "$LR/motivation.py" "$LR/planning.py" "$LR/_prod_world_context.py"', 'touch "$LR/world_context.py" "$LR/workspace.py" "$LR/motivation.py" "$LR/planning.py" "$LR/ethics.py" "$LR/_prod_world_context.py"', 1)
s = R(s, '"pass: 6 turns, all with the gate down" "$(wc -l < "$S/sent")$(grep -c FORWARDED "$S/gate.journal")" 60', '"pass: 10 turns, all with the gate down" "$(wc -l < "$S/sent")$(grep -c FORWARDED "$S/gate.journal")" 100', 1)
s = R(s, '"$(grep -c \'S6_STOPPED S6 already ran once\' "$R/out.s6_shadow_test.sh")$(wc -l < "$S/sent")" 16', '"$(grep -c \'S6_STOPPED S6 already ran once\' "$R/out.s6_shadow_test.sh")$(wc -l < "$S/sent")" 110', 1)
s = R(s, '''"$(grep -c '"lane": *"reasoning"\\|"lane":"reasoning"' "$DLOG")" 2''', '''"$(grep -c '"lane": *"reasoning"\\|"lane":"reasoning"' "$DLOG")" 3''', 1)
s = R(s, 'sc goal_row;', '''sc eth_text eth_text; install_seq; step s6_shadow_test.sh
ok "eth_text: a role word in an ethics record is detected" "$(grep -c 'records_t7' "$R/out.s6_shadow_test.sh")$(marker s6.pass)" 1no
sc eth_wrong eth_wrong; install_seq; step s6_shadow_test.sh
ok "eth_wrong: the wrong concern is detected" "$(grep -c 'records_t7' "$R/out.s6_shadow_test.sh")$(marker s6.pass)" 1no
sc eth_casual eth_casual; install_seq; step s6_shadow_test.sh
ok "eth_casual: reads on a casual turn are detected" "$(grep -c ' core_api' "$R/out.s6_shadow_test.sh")$(marker s6.pass)" 1no
sc goal_row;''', 1)
s = R(s, "$PKG/p1src", "$PKG/e1src") if "$PKG/p1src" in s else R(s, "$PKG/e1src", "$PKG/e1src")
(T / "window_sim_e1.sh").write_bytes(s.encode("ascii"))

c = (p1pkg / "tests" / "shell_init_check.py").read_text(encoding="ascii")
for a, b in (("s2b_transfer_p1.sh", "s2b_transfer_e1.sh"), ("s2_transfer_p1.sh", "s2_transfer_e1.sh"), ("p0_p1.sh", "p0_e1.sh"), ("s1_stop_m1.sh", "s1_stop_p1.sh"), ("s3_install_p1.sh", "s3_install_e1.sh"), ("s4_start_p1.sh", "s4_start_e1.sh"), ("r3_start_m1.sh", "r3_start_p1.sh")):
    c = R(c, a, b)
(T / "shell_init_check.py").write_bytes(c.encode("ascii"))
shutil.copy2(Path(__file__), pkg / "tools" / "gen_e1pkg.py")
(pkg / "tools" / "run_sim.sh").write_text("""#!/usr/bin/env bash
# Runs the simulation in one WSL session. bash tools/run_sim.sh <post-drafts db>  (from the package root)
T=$(mktemp -d); mkdir -p $T/e1src/payload; tar -xzf bundle/e1-bundle.tgz -C $T/e1src; cp "$1" $T/post.db
A=$(mktemp -u).tar; tar -cf $A scripts tests bundle -C $T post.db e1src
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -u root --exec bash -c 'rm -rf /tmp/e1p; mkdir -p /tmp/e1p; cat > /tmp/e1p.tar' < $A
MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu-24.04 -u root --exec bash -c 'cd /tmp/e1p && tar -xf /tmp/e1p.tar && sed -i "s/\\r$//" tests/*.sh; bash tests/window_sim_e1.sh /tmp/e1p /tmp/e1p/post.db 2>&1'
rm -rf $T $A
""", encoding="ascii", newline="\n")
print("BUNDLE", sha(tgz), sha(b64), len(b64))
