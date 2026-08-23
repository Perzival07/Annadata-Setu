import logging
import os
from typing import Dict, List, Optional

from brain.services.embeddings import EMBEDDER_ID, model_is_baked

logger = logging.getLogger("brain.rag")

CHROMA_DIR = os.getenv("CHROMA_DIR", "brain/data/chroma")
COLLECTION_NAME = "icar_package_of_practices"

# Provenance markers. These decide whether a chunk may be cited to the farmer.
FROM_CORPUS = "corpus"    # retrieved from the ingested document store
FROM_BUILTIN = "builtin"  # the small safety net below — NOT a citable document

# A minimal built-in reference so the service still returns sane agronomy when no
# corpus has been ingested. It is deliberately NOT labelled with document
# filenames: attributing these lines to an ICAR PDF that was never ingested puts
# a citation the farmer cannot check on the bottom of their advisory.
BUILTIN_KNOWLEDGE = [
    # --- Tomato -------------------------------------------------------------
    {
        "crop": "Tomato",
        "disease": "Early Blight",
        "content": (
            "Early Blight (Alternaria solani) in Tomato: dark brown spots with concentric rings "
            "giving a target-board appearance, starting on the lowest older leaves and moving "
            "upward; severe attacks defoliate the plant and expose fruit to sunscald. Favoured by "
            "warm days (24-29C) with humidity above 80% or extended leaf wetness. Commonly managed "
            "with Mancozeb 75% WP @ 2g/L or Chlorothalonil 75% WP @ 2g/L. Approx Rs 300-400 per "
            "acre. Remove and destroy lower infected leaves, avoid overhead irrigation, and stake "
            "plants so the canopy dries quickly."
        ),
    },
    {
        "crop": "Tomato",
        "disease": "Late Blight",
        "content": (
            "Late Blight (Phytophthora infestans) in Tomato: irregular water-soaked lesions turning "
            "dark brown to black, often with white fungal growth on the leaf underside in the "
            "morning; spreads to stems and fruit and can destroy a field within a week. Favoured by "
            "cool moist weather, 12-20C with prolonged wetness. Commonly managed with Cymoxanil + "
            "Mancozeb @ 2g/L or Metalaxyl + Mancozeb @ 2.5g/L. Approx Rs 550 per acre. This moves "
            "fast, so treat it as urgent rather than routine."
        ),
    },
    {
        "crop": "Tomato",
        "disease": "Nitrogen Deficiency",
        "content": (
            "Nitrogen Deficiency in Tomato: uniform yellowing of the older lower leaves starting "
            "from the tips, with the plant staying small and pale while new growth remains greener. "
            "Abiotic - do NOT spray fungicides, they cost money and fix nothing. Managed with "
            "neem-coated urea @ 25kg/acre or a 1% 19:19:19 NPK foliar spray. Approx Rs 150."
        ),
    },
    # --- Onion --------------------------------------------------------------
    {
        "crop": "Onion",
        "disease": "Purple Blotch",
        "content": (
            "Purple Blotch (Alternaria porri) in Onion: small water-soaked lesions on leaves and "
            "flower stalks that develop a white centre and a distinctive purple margin, enlarging "
            "into zoned patches that girdle and collapse the leaf. Favoured by humidity above 80% "
            "with temperatures of 21-30C, worst in late kharif. Commonly managed with Mancozeb 75% "
            "WP @ 2.5g/L or Tebuconazole @ 1ml/L. Add a sticker, because onion leaves are waxy and "
            "spray runs straight off."
        ),
    },
    # --- Rice (Paddy) -------------------------------------------------------
    {
        "crop": "Rice",
        "disease": "Blast",
        "content": (
            "Rice Blast (Pyricularia oryzae) in Rice/Paddy: spindle or eye-shaped lesions with grey "
            "centres and brown margins on leaves; the dangerous form is neck blast, which blackens "
            "the panicle base and produces empty whiteheads, cutting yield sharply even when leaves "
            "look acceptable. Favoured by night temperatures of 20-26C, long dew periods, cloudy "
            "weather and heavy nitrogen. Commonly managed with Tricyclazole 75% WP @ 0.6g/L or "
            "Isoprothiolane 40% EC @ 1.5ml/L. Approx Rs 700-900 per acre. Split nitrogen doses "
            "rather than applying all at once, and avoid urea top-dressing during a humid spell."
        ),
    },
    {
        "crop": "Rice",
        "disease": "Bacterial Leaf Blight",
        "content": (
            "Bacterial Leaf Blight (Xanthomonas oryzae pv. oryzae) in Rice: yellow to straw-coloured "
            "wavy lesions beginning at the leaf tip or margin and advancing down the blade; in "
            "seedlings the whole plant can wilt, a phase called kresek. Bacterial ooze appears as "
            "beads on a cut leaf held in clear water, which is the field test that separates it from "
            "a fungal blight. Favoured by standing water, storms that wound leaves, and heavy "
            "nitrogen. Fungicides do not work on it. Managed by draining the field, stopping "
            "nitrogen, and where recommended a Streptocycline plus Copper oxychloride spray. "
            "Prevention through resistant varieties and clean seed matters more than any spray."
        ),
    },
    {
        "crop": "Rice",
        "disease": "Sheath Blight",
        "content": (
            "Sheath Blight (Rhizoctonia solani) in Rice: oval greenish-grey water-soaked lesions on "
            "the leaf sheath near the water line, enlarging into irregular banded patches with "
            "purple-brown borders and climbing toward the flag leaf; sclerotia the size of mustard "
            "seeds sit on the sheath and survive in soil. Favoured by dense planting, high nitrogen "
            "and humidity above 90%. Commonly managed with Validamycin 3% L @ 2ml/L or Hexaconazole "
            "5% EC @ 2ml/L directed at the base of the plant, not the canopy."
        ),
    },
    {
        "crop": "Rice",
        "disease": "Brown Spot",
        "content": (
            "Brown Spot (Bipolaris oryzae) in Rice: numerous small oval brown spots with grey "
            "centres scattered evenly across the leaf, plus dark spotting on grain. Strongly "
            "associated with poor soil fertility, potassium or silicon deficiency and water stress, "
            "so it is as much a soil problem as a disease - it was the field symptom of the Bengal "
            "famine crop failure. Correct the nutrition first; Mancozeb 75% WP @ 2g/L manages the "
            "fungus where the attack is heavy."
        ),
    },
    # --- Wheat --------------------------------------------------------------
    {
        "crop": "Wheat",
        "disease": "Yellow Rust",
        "content": (
            "Yellow Rust, also called stripe rust (Puccinia striiformis), in Wheat: bright "
            "yellow-orange pustules arranged in narrow stripes running along the leaf veins, "
            "rubbing off as powder onto the hand. Favoured by cool weather of 10-15C with dew, "
            "which is why it moves through north Indian wheat in January and February. Commonly "
            "managed with Propiconazole 25% EC @ 1ml/L or Tebuconazole 25% EC @ 1ml/L. Approx "
            "Rs 600-800 per acre. Spray at first appearance - rust doubles quickly, and a week of "
            "delay costs far more than the spray."
        ),
    },
    {
        "crop": "Wheat",
        "disease": "Karnal Bunt",
        "content": (
            "Karnal Bunt (Tilletia indica) in Wheat: partial infection of individual grains, which "
            "turn black and powdery along the crease and give off a fishy smell from "
            "trimethylamine; usually found at threshing rather than in the standing crop. Favoured "
            "by cool humid weather with light rain at heading. It affects grain acceptability and "
            "export grading more than yield. Managed preventively with Propiconazole at the boot "
            "stage; treat seed and avoid saving grain from an affected field."
        ),
    },
    {
        "crop": "Wheat",
        "disease": "Powdery Mildew",
        "content": (
            "Powdery Mildew (Blumeria graminis) in Wheat: white to grey powdery patches on the upper "
            "leaf surface and sheath, later developing small black dots; leaves yellow and die early "
            "from the bottom up. Favoured by cool humid weather of 15-22C, dense stands and heavy "
            "nitrogen. Commonly managed with wettable sulphur @ 2.5g/L or Propiconazole 25% EC @ "
            "1ml/L."
        ),
    },
    # --- Maize --------------------------------------------------------------
    {
        "crop": "Maize",
        "disease": "Turcicum Leaf Blight",
        "content": (
            "Turcicum Leaf Blight (Exserohilum turcicum) in Maize: long elliptical grey-green to tan "
            "lesions shaped like cigars, one to fifteen centimetres long, starting on lower leaves "
            "and moving up; heavy infection before silking is what costs yield. Favoured by moderate "
            "temperatures of 18-27C with heavy dew or rain. Commonly managed with Mancozeb 75% WP @ "
            "2.5g/L or Azoxystrobin 23% SC @ 1ml/L. Rotate away from maize and plough in residue, "
            "since the fungus overwinters on it."
        ),
    },
    {
        "crop": "Maize",
        "disease": "Fall Armyworm",
        "content": (
            "Fall Armyworm (Spodoptera frugiperda) in Maize: ragged window-pane feeding on young "
            "leaves, then larvae move into the whorl leaving moist sawdust-like frass; an inverted "
            "Y on the head capsule and four dark spots in a square on the second-last segment "
            "identify it. This is an insect, not a disease - fungicide does nothing. Managed with "
            "Emamectin benzoate 5% SG @ 0.4g/L or Chlorantraniliprole 18.5% SC @ 0.4ml/L directed "
            "INTO the whorl, sprayed early morning or late evening when larvae are active. Approx "
            "Rs 500-700 per acre. Hand-picking and sand-plus-lime in the whorl work on small plots."
        ),
    },
    # --- Cotton -------------------------------------------------------------
    {
        "crop": "Cotton",
        "disease": "Bacterial Blight",
        "content": (
            "Bacterial Blight (Xanthomonas citri pv. malvacearum) in Cotton: small dark green "
            "water-soaked angular spots on leaves that are bounded by the veins, giving the "
            "characteristic angular leaf spot, later turning brown; black arm develops as dark "
            "lesions girdling the stem, and bolls rot. Favoured by 30-40C with high humidity and "
            "wind-driven rain. Copper oxychloride 50% WP @ 3g/L with Streptocycline is the usual "
            "management. Use acid-delinted certified seed - the bacterium is seed-borne, so this "
            "starts in the bag more often than in the field."
        ),
    },
    {
        "crop": "Cotton",
        "disease": "Pink Bollworm",
        "content": (
            "Pink Bollworm (Pectinophora gossypiella) in Cotton: rosetted flowers whose petals twist "
            "shut, and bolls that look sound outside while pink larvae feed on the lint and seed "
            "inside; exit holes and stained lint appear later. The damage is hidden, so scout by "
            "cutting open green bolls rather than judging by the canopy. Managed with pheromone traps "
            "at 8 per acre for monitoring and mass trapping, timely termination of the crop to break "
            "the cycle, and where thresholds are crossed Emamectin benzoate or Chlorpyriphos as "
            "recommended locally. Do not carry the crop into an extended late season - that is what "
            "builds the population for the following year."
        ),
    },
    {
        "crop": "Cotton",
        "disease": "Leaf Curl Virus",
        "content": (
            "Cotton Leaf Curl Virus in Cotton: upward or downward curling of leaves with thickened "
            "darkened veins, small enations on the underside, stunted growth and few bolls. "
            "Transmitted by whitefly - the virus itself cannot be sprayed, so control targets the "
            "vector. Managed with yellow sticky traps, Diafenthiuron 50% WP @ 1.2g/L or Flonicamid "
            "50% WG @ 0.3g/L against whitefly, and removal of alternate hosts. Resistant varieties "
            "are the durable answer."
        ),
    },
    # --- Sugarcane ----------------------------------------------------------
    {
        "crop": "Sugarcane",
        "disease": "Red Rot",
        "content": (
            "Red Rot (Colletotrichum falcatum) in Sugarcane: the third or fourth leaf yellows and "
            "dries while lower leaves still look green, and a split cane shows red internal tissue "
            "crossed by distinctive white patches, with a sour alcoholic smell. This is the most "
            "serious sugarcane disease in the subcontinent and there is no effective curative spray. "
            "Managed by uprooting and burning affected clumps, avoiding ratooning an infected field, "
            "treating setts with Carbendazim 50% WP @ 1g/L, and moving to resistant varieties. "
            "Drainage matters - waterlogging makes it far worse."
        ),
    },
    {
        "crop": "Sugarcane",
        "disease": "Wilt",
        "content": (
            "Sugarcane Wilt (Fusarium sacchari) in Sugarcane: gradual yellowing and drying of the "
            "crown, canes becoming light and hollow with a purplish-brown internal discolouration "
            "and a hollow pith. Often follows waterlogging, drought stress or borer damage that "
            "opens the way in. Managed through sett treatment, drainage, avoiding ratoons from "
            "affected fields and resistant varieties."
        ),
    },
    {
        "crop": "Sugarcane",
        "disease": "Smut",
        "content": (
            "Sugarcane Smut (Sporisorium scitamineum) in Sugarcane: a long black whip-like structure "
            "emerging from the growing point, covered in powdery spores; affected clumps become thin "
            "and grassy with narrow leaves. Managed by removing whips carefully in a bag before they "
            "burst and spread spores, discarding infected seed material, hot water treatment of "
            "setts, and resistant varieties."
        ),
    },
    # --- Chickpea (Gram) ----------------------------------------------------
    {
        "crop": "Chickpea",
        "disease": "Fusarium Wilt",
        "content": (
            "Fusarium Wilt (Fusarium oxysporum f. sp. ciceris) in Chickpea/Gram: sudden drooping of "
            "leaves and petioles with the plant drying in patches across the field; a split stem "
            "near the collar shows brown discolouration of the internal vascular tissue. Favoured by "
            "soil temperatures around 25C and dry spells. The fungus persists in soil for years, so "
            "rotation and resistant varieties matter more than any spray. Seed treatment with "
            "Trichoderma viride @ 4g/kg or Carbendazim @ 2g/kg is the practical control."
        ),
    },
    {
        "crop": "Chickpea",
        "disease": "Ascochyta Blight",
        "content": (
            "Ascochyta Blight (Ascochyta rabiei) in Chickpea/Gram: circular to elongated lesions with "
            "dark margins bearing tiny black pycnidia arranged in concentric rings, on leaves, pods "
            "and stems; girdled stems break and the crop collapses in patches. Favoured by cool "
            "cloudy weather of 20-25C with rain. Commonly managed with Chlorothalonil 75% WP @ 2g/L "
            "or Mancozeb 75% WP @ 2.5g/L, plus clean disease-free seed."
        ),
    },
    {
        "crop": "Chickpea",
        "disease": "Pod Borer",
        "content": (
            "Gram Pod Borer (Helicoverpa armigera) in Chickpea/Gram: larvae feed on foliage and then "
            "bore into pods with the head inside and body hanging out, eating the developing seed; "
            "one larva damages many pods. This is an insect, not a disease. Managed with pheromone "
            "traps to time the spray, bird perches at 10 per acre, HaNPV @ 250 LE per acre, or "
            "Emamectin benzoate 5% SG @ 0.4g/L where thresholds are crossed. Scout at flowering, "
            "because that is when the eggs are laid."
        ),
    },
    # --- Pigeon Pea (Tur / Arhar) -------------------------------------------
    {
        "crop": "Pigeon Pea",
        "disease": "Fusarium Wilt",
        "content": (
            "Wilt (Fusarium udum) in Pigeon Pea/Tur/Arhar: plants wilt from flowering onwards, often "
            "with a purple-brown band running up one side of the stem from the base; a split stem "
            "shows blackened vascular streaks, and partial wilting of one branch is typical. "
            "Soil-borne and persistent, so long rotation and resistant varieties are the real "
            "control. Seed treatment with Trichoderma viride @ 4g/kg helps."
        ),
    },
    {
        "crop": "Pigeon Pea",
        "disease": "Sterility Mosaic",
        "content": (
            "Sterility Mosaic in Pigeon Pea/Tur: bushy stunted plants with pale mosaic mottling on "
            "small leaves and, critically, no flowers or pods at all - the plant stays green and "
            "produces nothing, which is why it is called green plague. Spread by eriophyid mites, "
            "not by seed. Managed by removing volunteer and ratoon plants that carry it over, "
            "resistant varieties, and miticide where infestation is early and heavy."
        ),
    },
    # --- Mustard ------------------------------------------------------------
    {
        "crop": "Mustard",
        "disease": "Alternaria Blight",
        "content": (
            "Alternaria Blight (Alternaria brassicae) in Mustard/Rapeseed: greyish to dark brown "
            "round spots with concentric rings on leaves, enlarging and merging until leaves dry; "
            "spots on pods reduce seed set and oil content. Favoured by 20-25C with high humidity, "
            "typically after a winter shower. Commonly managed with Mancozeb 75% WP @ 2g/L, first "
            "spray at 45 days and repeated at 15-day intervals."
        ),
    },
    {
        "crop": "Mustard",
        "disease": "White Rust",
        "content": (
            "White Rust (Albugo candida) in Mustard: shiny white raised pustules on the leaf "
            "underside with yellowing above; systemic infection distorts the flower stalk into a "
            "swollen curved staghead that sets no seed. Favoured by cool moist weather. Commonly "
            "managed with Metalaxyl + Mancozeb @ 2.5g/L, and by removing stagheads before they shed "
            "spores."
        ),
    },
    {
        "crop": "Mustard",
        "disease": "Aphid",
        "content": (
            "Mustard Aphid (Lipaphis erysimi) in Mustard: dense grey-green colonies clustered on "
            "shoots, flower stalks and developing pods, sucking sap so the plant curls, stunts and "
            "sets shrivelled seed; sticky honeydew and sooty mould follow. The single largest yield "
            "loss in Indian mustard. An insect, not a disease. Managed with Imidacloprid 17.8% SL @ "
            "0.3ml/L or Dimethoate 30% EC @ 1.7ml/L, sprayed in the afternoon and avoiding flowering "
            "peak where possible to spare pollinators."
        ),
    },
    # --- Groundnut ----------------------------------------------------------
    {
        "crop": "Groundnut",
        "disease": "Tikka Leaf Spot",
        "content": (
            "Tikka Leaf Spot (Cercospora arachidicola and Cercosporidium personatum) in "
            "Groundnut/Peanut: circular dark brown spots, early leaf spot with a yellow halo and "
            "late leaf spot nearly black on the underside without a halo; heavy infection defoliates "
            "the crop before pods fill. Favoured by humid weather of 25-30C. Commonly managed with "
            "Chlorothalonil 75% WP @ 2g/L or Carbendazim + Mancozeb @ 2g/L, starting at 30-35 days."
        ),
    },
    {
        "crop": "Groundnut",
        "disease": "Rust",
        "content": (
            "Groundnut Rust (Puccinia arachidis) in Groundnut: orange-brown powdery pustules on the "
            "leaf underside that rupture and release spores, with the leaf drying but staying "
            "attached to the plant - which distinguishes it from leaf spot defoliation. Often occurs "
            "together with tikka. Managed with Mancozeb 75% WP @ 2.5g/L or Hexaconazole 5% EC @ "
            "2ml/L."
        ),
    },
    {
        "crop": "Groundnut",
        "disease": "Collar Rot",
        "content": (
            "Collar Rot (Aspergillus niger) in Groundnut: seedlings collapse within a few weeks of "
            "sowing, with a soft rotted collar at soil level covered in black sooty spore masses. "
            "Favoured by high soil temperature and dry sowing conditions, and by damaged or poorly "
            "stored seed. Seed treatment with Trichoderma viride @ 4g/kg or Carbendazim @ 2g/kg is "
            "the control - once the seedling is down there is nothing to save."
        ),
    },
    # --- Soybean ------------------------------------------------------------
    {
        "crop": "Soybean",
        "disease": "Rust",
        "content": (
            "Soybean Rust (Phakopsora pachyrhizi) in Soybean: tiny tan to reddish-brown angular "
            "lesions on the leaf underside bearing raised pustules, starting on lower leaves and "
            "causing rapid defoliation from the bottom up before pods fill. Favoured by prolonged "
            "leaf wetness and 20-28C. Commonly managed with Hexaconazole 5% EC @ 2ml/L or "
            "Propiconazole 25% EC @ 1ml/L at first appearance - it moves quickly once established."
        ),
    },
    {
        "crop": "Soybean",
        "disease": "Yellow Mosaic",
        "content": (
            "Yellow Mosaic Virus in Soybean: bright yellow irregular patches mixed with green on the "
            "leaves, later turning necrotic, with stunted plants and few small pods carrying "
            "shrivelled seed. Spread by whitefly, so the virus itself cannot be sprayed and control "
            "targets the vector. Managed with yellow sticky traps, roguing infected plants early, "
            "Thiamethoxam 25% WG @ 0.2g/L against whitefly, and resistant varieties, which are the "
            "durable answer."
        ),
    },
    {
        "crop": "Soybean",
        "disease": "Charcoal Rot",
        "content": (
            "Charcoal Rot (Macrophomina phaseolina) in Soybean: plants wilt and die in patches "
            "during dry spells after flowering; peeling the lower stem and taproot reveals grey "
            "tissue peppered with tiny black microsclerotia, like charcoal dust. Favoured by "
            "moisture stress with soil temperatures above 30C, so it is a drought-linked disease. "
            "Managed by seed treatment with Trichoderma viride @ 4g/kg, maintaining soil moisture, "
            "avoiding dense stands, and rotating with cereals."
        ),
    },
    # --- Potato -------------------------------------------------------------
    {
        "crop": "Potato",
        "disease": "Late Blight",
        "content": (
            "Late Blight (Phytophthora infestans) in Potato: irregular water-soaked greyish lesions "
            "on leaf tips and margins with white fungal growth beneath in humid mornings, spreading "
            "to stems and tubers, which develop a firm reddish-brown granular rot. Favoured by cool "
            "moist weather of 12-20C with fog or dew. This is the disease of the Irish famine and it "
            "moves within days. Managed preventively with Mancozeb 75% WP @ 2g/L, and curatively "
            "with Cymoxanil + Mancozeb @ 3g/L once symptoms appear. Earth up well so tubers are not "
            "exposed to spores washing down."
        ),
    },
    {
        "crop": "Potato",
        "disease": "Early Blight",
        "content": (
            "Early Blight (Alternaria solani) in Potato: dark brown spots with concentric target-like "
            "rings on older lower leaves, surrounded by a yellow halo, progressing upward. Favoured "
            "by warm weather with alternating wet and dry spells, and worse on nitrogen-starved or "
            "stressed crops. Commonly managed with Mancozeb 75% WP @ 2g/L. Correct nutrition, "
            "because a hungry crop gets it worse."
        ),
    },
    {
        "crop": "Potato",
        "disease": "Black Scurf",
        "content": (
            "Black Scurf (Rhizoctonia solani) in Potato: hard black soil-like crusts stuck to the "
            "tuber skin that do not wash off, plus stem canker on underground sprouts causing "
            "patchy emergence and aerial tubers. The tuber is edible but unsellable, so this is a "
            "market-grade problem as much as a yield one. Managed by planting healthy certified "
            "seed, treating tubers with Pencycuron or Boric acid dip, and harvesting promptly rather "
            "than leaving the crop in the ground."
        ),
    },
]

# Kept for callers that still import the old name.
FALLBACK_KNOWLEDGE = BUILTIN_KNOWLEDGE


class RAGService:
    def __init__(self, chroma_dir: str = CHROMA_DIR):
        self.chroma_dir = chroma_dir
        self.collection = None
        self.embedder_mismatch: Optional[str] = None
        self._init_chroma()

    def _init_chroma(self):
        try:
            import chromadb
            if not os.path.exists(self.chroma_dir):
                logger.warning(
                    f"No ChromaDB store at {self.chroma_dir}. Retrieval will use built-in "
                    f"notes only and no document will be cited."
                )
                return
            client = chromadb.PersistentClient(path=self.chroma_dir)
            collection = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"embedder": EMBEDDER_ID},
            )

            # Vectors from two different models are not comparable, and querying
            # across them returns plausible-looking wrong chunks rather than an
            # error. Refuse instead.
            built_with = (collection.metadata or {}).get("embedder")
            if built_with and built_with != EMBEDDER_ID:
                logger.error(
                    f"Store at {self.chroma_dir} was built with {built_with!r} but this "
                    f"service embeds with {EMBEDDER_ID!r}. Refusing to query it — "
                    f"re-run `python -m brain.services.ingest --reset`."
                )
                self.embedder_mismatch = built_with
                return

            self.collection = collection
            count = self.collection.count()
            if count == 0:
                # Loud, because the failure is otherwise invisible: retrieval keeps
                # working, just without any of the documents the pitch is built on.
                logger.warning(
                    "=" * 72 + "\n"
                    f"ChromaDB collection '{COLLECTION_NAME}' is EMPTY ({self.chroma_dir}).\n"
                    "RAG is running on built-in notes only. No advisory will cite a source.\n"
                    "Populate it with:  python -m brain.services.ingest\n"
                    "after placing the source PDFs in brain/data/icar_pdfs/.\n"
                    + "=" * 72
                )
            else:
                logger.info(f"ChromaDB ready at {self.chroma_dir}: {count} chunks indexed.")
        except Exception as e:
            # Chroma raises this when the persisted collection was built by a
            # different embedder. That is a real mismatch, not a transient
            # failure, and the operator needs the remedy rather than a stack trace.
            if "mbedding function" in str(e):
                self.embedder_mismatch = "default (ChromaDB built-in)"
                logger.error(
                    f"Store at {self.chroma_dir} was embedded with a different model than "
                    f"{EMBEDDER_ID}. Vectors from two models are not comparable, so retrieval "
                    f"is disabled. Rebuild it:  python -m brain.services.ingest --reset"
                )
            else:
                logger.warning(f"ChromaDB initialization failed, using built-in notes: {e}")

    @property
    def corpus_size(self) -> int:
        """Number of indexed chunks. Zero means nothing is citable."""
        if not self.collection:
            return 0
        try:
            return self.collection.count()
        except Exception:
            return 0

    def status(self) -> Dict[str, object]:
        """Corpus health, surfaced on /health so a degraded demo is visible."""
        size = self.corpus_size
        status = {
            "chroma_dir": self.chroma_dir,
            "collection": COLLECTION_NAME,
            "embedder": EMBEDDER_ID,
            "model_cached": model_is_baked(),
            "indexed_chunks": size,
            "retrieval_mode": "corpus" if size else "builtin_only",
            "sources_citable": bool(size),
        }
        if self.embedder_mismatch:
            status["error"] = f"store built with {self.embedder_mismatch}, incompatible"
        return status

    def retrieve_context(self, crop: str, query: str, top_k: int = 4) -> List[Dict[str, Optional[str]]]:
        """Return up to top_k reference chunks, each tagged with its provenance.

        Only chunks tagged FROM_CORPUS carry a `source` that may be shown to the
        farmer. Built-in chunks return source=None so a caller cannot accidentally
        cite them as a document.
        """
        if self.corpus_size > 0:
            try:
                results = self.collection.query(query_texts=[f"{crop} {query}"], n_results=top_k)
                docs = (results.get("documents") or [[]])[0]
                if docs:
                    metas = (results.get("metadatas") or [[{}] * len(docs)])[0]
                    return [
                        {
                            "content": doc,
                            "source": (meta or {}).get("source"),
                            "provenance": FROM_CORPUS,
                        }
                        for doc, meta in zip(docs, metas)
                    ]
            except Exception as e:
                logger.warning(f"ChromaDB query failed, using built-in notes: {e}")

        crop_lower = (crop or "").lower()
        matching = [
            c for c in BUILTIN_KNOWLEDGE
            if c["crop"].lower() in crop_lower or crop_lower in c["crop"].lower()
        ]
        if not matching:
            matching = BUILTIN_KNOWLEDGE[:top_k]

        return [
            {"content": c["content"], "source": None, "provenance": FROM_BUILTIN}
            for c in matching[:top_k]
        ]


rag_service = RAGService()
