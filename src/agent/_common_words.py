"""Yaygın İngilizce kelimeler — yumuşak varlık çıkarımının stopword listesi.

Grounding v2.1 / S1'de gerçek rapor iddialarıyla kalibre edildi: LLM raporlarının
paraphrase kelimeleri (includes, improvements, automatically...) burada olmalı,
yoksa her sadık iddia haksız FLAG yer. Teknik terimler (python, samba, systemd,
tailscale...) BİLİNÇLİ olarak listede DEĞİL — onlar doğrulanacak varlıklar.

NOT: Liste İngilizce — rapor dili İngilizce olduğu sürece geçerli (kilitli karar).
Rapor dili değişirse bu katman yeniden kalibre edilmeli.

Kalibrasyon ekleri: graphic/graphical/graphics (2026-07-29, 2026-07-10 tur
bulgusu — betimleyici sıfat, teknik varlık değil; -al türetmesi _morph_variants
kapsamı dışında olduğundan liste yoluyla çözüldü, açık karar #3).
made + compiler (2026-07-29 E2E tur bulguları — 'made' düzensiz geçmiş [kök
değişimi morfoloji kuralının bilinçli sınırı dışında, haksız FLAG], 'compiler'
genel paraphrase ismi [ince 22.04 korpusunda geçmeyince sadık GCC iddiası
yanlış-RED yedi]; ikisi de teknik varlık değil).
"""

COMMON_WORDS = frozenset("""
ability able accept accepted accepts access accessed accessible accessing
accompany accomplish according account accounts achieve achieved achieves
acquire across act action actions activate activated activates active
actively actual actually adapt adapted adding adds address addressed
addresses adequate adopt adopted adoption advance advanced advantage
advantages advice advise affects afford agree agreed agreement ahead aim
aimed aims alert alerts align aligned alike alive alter altered alternate
announce announced announcement anticipate anticipated apparent apparently
appear appeared appears append appended applied applies appropriate
approval approve approved arrange arranged arrival arrive arrived aspect
aspects assign assigned assist assistance associate associated assume
assumed assumes assure attempt attempted attempts attend attention
attribute attributes audience authorize authorized avoided await awaited
balance balanced barely basic basically basis bear became begins behave
belong belonged belongs benefit benefits besides bigger biggest breaks
briefly broad broader broadly builds calculate calculated calling calls
capable capture captured care cared careful carrying catch caught cease
ceased central certainly challenge challenges chance chances choosing
chose chosen claim claimed claims clarify class classes clean cleaned
cleaner cleanup clear cleared clearly click clicked clicks combine
combined combines comfort coming comment comments commit committed
compare compared compares comparison compatible compile compiled compiler compiles
complain complete completes complex complexity comply comprise comprised
compute computed conclude concluded conclusion condition conditions
conduct conducted confidence confident configure configures confirm
confirmed confirms conflict conflicts confuse confused connect connected
connects consequence consequently conserve consist consisted consistent
consistently consisting constant constantly construct constructed consult
consume consumed consumes contact contained containing contains content
contents context contract contrast contribute contributed control
controlled convenience convenient convention convert converted converts
convey convince cope copied copies copy core corner correct corrected
correction correctly correspond corresponding cost costs cover covered
covers crash crashed crashes create creates creating creation criteria
critical cross crucial current customize customized deal dealing deals
dealt decide decided decides decision decisions declare declared decline
declined decrease decreased dedicate dedicated deep deeper deeply
definite definitely definition degree delay delayed delays deliver
delivered delivers delivery demand demanded demands demonstrate
demonstrated denied deny depart depend depended dependent depending
depends deploy deployed deployment describe describes desire desired
destination detailed determine determined determines develop developed
develops difference differences differently difficult difficulty direct
directed direction directions directly disagree disappear discover
discovered discuss discussed discussion dispose distinct distinguish
distribute distributed divide divided division doing double doubt
downloads dozen dramatically draw drawn drew drive driven drives driving
drop dropping drops early earn earned ease easier easiest easily easy
edge edges edit edited editing edits effective effectively efficiency
efficient efficiently effort efforts elect elected element elements
eliminate eliminated elsewhere embrace emerge emerged emphasis emphasize
employ employed enabled enables enabling encourage encouraged
encourages engage engaged enhance enhanced enhances enormous ensure
ensured ensures ensuring enter entered enters entirely entity entries
entry equal equally equivalent escape escaped essential essentially
establish established estimate estimated evaluate evaluated evaluation
eventually everybody everyone everywhere evidence evolve evolved exact
examine examined examples exceed exceeded excellent exception exceptions
exchange exclude excluded exclusive execute executed executes execution
exercise exhibit expand expanded expands expansion expectation expects
expensive experienced experiment explain explained explains explanation
explore explored expose exposed express expressed extend extends extent
external extract extracted facilitate facing fact factor factors fail
failing fairly fall fallen falling falls familiar fashion favor feasible
feedback feel fell felt field fields figure figures filed fill filled
final finally finding findings fine finish finished finishes fits fitted
fix fixing flexible flow focus focused focuses follows force forced forces
forget forgot form formal format formats formed forms forth forward found
foundation framework free freely frequent frequently front fulfill
function functional functioning fundamental future gain gained gains
gather gathered gave generic gets giving goal goals goes gone govern
grab gradually grant granted graphic graphical graphics great greatly ground grow growing grown
grows growth guarantee guaranteed guess guidance guided guidelines handle
handles happening head heavily helpful helping hold holding holds hope
hoped hopefully hoping huge idea ideal ideally ideas identical identify
identified identifies ignore ignored illustrate imagine immediate
immediately implement implementation implemented implements implication
implies imply importance importantly impose improved improving inability
incorporate incorporated increase increases increasing increasingly
incremental independent independently index indicate indicated indicates
indication individual individually influence inform informal informed
inherent initial initialize initially initiate initiated initiates
initiating input insert inserted inside insight insist inspect inspected
install instance instances integrate integrated integrates integration
intend intended intends intent intention interact interaction interest
interested interesting intermediate internally interpret interpreted
interrupt intervention interventions introduce invalid investigate
investigated invoke invoked involve involved involves isolate isolated
isolation iterate iteration itself joined joins jump jumped justify keeping
knew knowing knowledge known lack lacked lacking laid land landed lands
large largely lasted lasting lastly launch launches lays lead leading
leads learn learned learning leave leaves leaving left legacy legitimate
lend length lets letter letting lies life lifetime lift light lightweight
liked likewise limits link linked links listing live lived lives living
locate located locations lock locked logic logical logically loose lose
losing loss lost lots loud love lower lowered lowest made maintain maintenance
majority manner map mapped mapping maps mark marked marks match matched
matches matching material matter matters maximum meant measure measured
measures mechanisms meet meeting meets member members mention mentioned
mentions merely merge merged merges met metric metrics middle minimize
minimized minimum missing mistake mix mixed model models moderate modern
modification modifications modified modifies modify moment monitor
monitored monitoring move movement moves moving named namely names narrow
native naturally nature nearby necessarily necessary needing negative
neither network networking networks nevertheless nice nobody node nodes
nominal noncritical nonetheless notably notification notifications
notified notifies noting notion numerous obtain obtained obtains obvious
obviously occasion occasionally occur occurred occurrence occurring
occurs offering offers okay once ones ongoing online operate operated
operates operational opportunity oppose opposite optimal optimize
optimized ordinary organize organized orient oriented origin original
originally outcome outcomes outside overcome overhead overlap
overlapping override overridden overrides overview owner owners
ownership pack packed pair paired pairs parallel parameter parameters
partially participate particular pass passed passes passing past pattern
patterns pause paused pending percentage perfect perfectly performing
period periodic periodically permanent permanently permission permissions
permit permitted persist persistent personal perspective phase phases
pick picked picks piece pieces placement places placing plain plan
planned planning plans play played plays plenty plus pointing populate
populated portion position positioned positions positive possibility
possibly practical practice practices precise precisely predict
predictable predicted prefer preference preferences preferred prepare
prepared present presented presents preserve preserved press pressed
pretty prevent prevented prevents previous primary principle principles
priority privilege privileges proceed proceeded proceeds produce
produced produces producing production programming prohibit promote
promoted promotes promoting promotion prompt
prompted prompts proof propose proposed protect protected protection
protects prove proved proven provision proximity publish published pull
pulled pulls purchase pure purely push pushed pushes puts putting
qualified quality quantity quick quickly quiet raise raised raises range
ranges ranging rank ranked rapid rapidly rare rarely rate rates reach
reached reaches react ready real realize realized really reasonable
reasonably rebuild rebuilt recall recognize recognized recommendation
recommendations recommends record recorded records recover recovered
recovery reduce reduces reducing reduction refactor referred refers
reflect reflected refresh refreshed refuse regard regardless region
register registered regression reject rejected rejects relative
relatively relaxed relevant reliability reliable reliably relied relies
rely remaining remark remedy remember reminded reminder repeat repeated
repeatedly replacing report reporting represent represented represents
reproduce reproduced requested requesting rerun reset resets reside
resides resolve resolves resort respect respective respectively respond
responded response responses responsibility responsible restore restored
restores restrict restricted restriction restrictions resume resumed resumes
resuming retained retains
retire retired retrieve retrieved retry return returned returning reuse
reused reveal revealed reverse revert reverted review reviewed reviews
revise revised rewrite rewritten rich rise risen rising risk risks
robust roles rolled rolling rough roughly round route routed routes
routine rule rules runtime safe safely safer safety satisfied satisfy
save saved saves saving scale scaled scales scenario scenarios schedule
scheduled schedules scheme scope search searched searches searching
secure secured securely seek seeking seeks seem seemed seemingly seems
segment select selecting selects send sending sends sense sensible
sensitive sent separated separates sequence serious seriously serve
served serves serving shape shaped shift shifted short shortly signal
signaled significantly signs simplified simplify simplifies
simultaneously situation situations skip skipped skips slight slightly
slow slowly smooth smoothly solid solve solved solves somebody somehow
someone somewhat somewhere sooner sort sorted sorts sound sounds spare
speak special specification specifications specified specifies spent
split spot spread stand standards standing stands stated statements
stays steady stick stopping straight straightforward strategy stream
streamline streamlined strength strict strictly strong stronger strongly
structure structured structures struggle stuck study stuff style styles
subsequent subsequently subset substantial substantially substitute
succeed succeeded success successful successfully sufficient
sufficiently suggest suggested suggestion suggests suitable suited
supplied supplies surface surprise surprising surround suspect suspend
suspended sustain switching symbol symbols synchronize synchronized
taking talk talked target targeted technique techniques tell telling
tells temporarily tend tended tends term termed terms therefore
thorough thoroughly thought threshold throughout tied ties tight
tightly timing tiny tips title titles told tolerance tolerate took
touch touched track tracked tracking tracks trade tradeoff traditional
transfer transferred transform transformed translate translated treat
treated treatment tree trees trend trends tried tries trigger triggered
triggers trouble truly trust trusted truth try trying tune tuned turns
tweak typo ultimate ultimately unavailable unchanged uncommon undergo
underlying understand understanding understood undo unexpected
unexpectedly unfortunately uniform unique unit units unnecessary
unrelated unsupported unusual upcoming uploaded urge urgent usable
utilize utilized valid validate validated validates validation valuable
varies vary varying verification verified verifies vice view viewed
views visible vision visual visually vital wait waited waiting waits
walk want wanted wants warn warned warns watch watched ways weak
weakness wealth wear whenever wherever whole wide widely wider willing
wish wished wonder wondered worked workflow works worry worse worst
worth write writes writing written wrong yield yielded yields
""".split()) | frozenset("""
about above across added addition additional additionally adjust adjusted
adjustments affect affected affecting affects after afterwards again against
allow allowed allowing allows almost along already also alternative
alternatively although always among amount another anything anywhere
application applications apply approach architecture around attach attached
attaches automatic automatically available avoid aware based because become
becomes been before began begin behavior behaviour being below better between
beyond boot booted both bring brings brought bugs build built came cannot capability
capabilities careful carefully case cases cause caused causes certain change
changed changes changing check checked checks choice choices choose chosen
close closed come comes coming command commands common commonly communication
compatibility
compatible complete completed completely component components computer
computers configuration configurations configure configured confirm connection
connections connectivity consider considered considering consists contain
contained contains continue continued continues controls correct correctly
could count create created creates current currently custom daily data date
dates default defaults depend depending depends deprecate deprecated
deprecation describe described description desktop detail details detect
detected detection determine developer developers development device devices
differ difference differences different directly directory disable disabled
disables display displayed distribution distributions document documentation
documented does done down download downloaded drop dropped drops during each
earlier early easier easily easy edition effect effects effort either enable
enabled enables encounter encountered encounters enhancement enhancements
enough ensure entire entirely environment environments error errors especially
etc even every everything exact exactly example examples exist existing exists
expect expected experience explicitly extended extension extensions extra fail
failed fails failure failures faster feature features file files finally find
first fixed fixes folder folders follow following follows found four fresh from
full fully function functionality functions further general generally generate
generated getting given gives global going good greater group groups guide
handle handled handling happen happened happens hardware have having help
helps here high higher highly host hosts hour hours however images impact
important improve improved improvement improvements improves include included
includes including incompatible increase increased indicate information
initial initially install installation installed installer installing installs
instead instruction instructions interface interfaces interim internal
internet into introduce introduced introduces introducing issue issues item
items itself
just keep keeps kept know known large larger last later latest launch launched
least less level levels like likely limit limitation limitations limited line
lines list listed lists little load loaded local locally location login long
longer look lower machine machines mail main mainly maintain maintained major
make makes making manage managed management manager manages manual manually
many mechanism meaning means media memory menu message messages method methods
might migrate migrated migration minimal minor mirror missing mode modes month
months more most mostly mount mounted move moved much multiple must name named
names nearly need needed needs never newer newly next none normal normally
note noted notes nothing notice notify notified number numbers offer offered
offers officially often older only onto open opened operating operation
operations option optional optionally options order other others otherwise
output over overall overview package packages page pages part partial parts
password path paths perform performance performed performs place placed
platform platforms please point pointed points policy poor popular port ports
possible potential potentially previous previously primarily primary print
printing prior privacy probably problem problems procedure procedures process
processes product products profile profiles program programs progress project
projects proper properly protocol protocols provide provided provides
providing purpose purposes
question questions quite rather reach read reading reason reasons reattach
receive received receives recent recently recommend recommended reduce reduced
refer reference regarding regular regularly relate related release released
releases releasing remain remains remote remove removal removed removes
removing replace replaced
replacement replaces report reported reports request requests require required
requirement requirements requires resolution resolve resolved resource
resources restart restarted restarts result results retain return returns
review right root running runs same screen search second seconds section
sections security see seen select selected selection separate separately
server servers service services session sessions setting settings setup
several shall share shared ship shipped ships shorter should show shown shows
side significant similar similarly simple simply since single site sites size
small smaller software solution solutions some something sometimes soon source
sources space special specific specifically specify stable stage standard
start started starting starts state states statement status step steps still
stop stopped stops storage store stored subject such suite summary supply
support supported supporting supports sure switch switched symlink
synchronization syntax system systems table tables take taken takes target
targets task tasks team technical technology tell temporary test tested
testing tests text than that their theme them themselves then there therefore
these they thing things think third this those three through thus time times
today together tool tools topic total transition transport troubleshooting
turn turned twice type types typical typically unable under understand
unexpected unless unlike until update updated updates updating upgrade
upgraded upgrades upgrading upon upstream usable usage used useful user users
uses using usually value values variant variants variety various vendor
verify version versions view virtual visit want wanted warning warnings weekly
week weeks well were what when where whereas whether which while will window
windows with within without word words work working works would year years
your zero
""".split())
