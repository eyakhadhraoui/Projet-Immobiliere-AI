"""Checklists officielles et moteur de règles d'audit documentaire immobilier tunisien."""

from __future__ import annotations

from typing import Any

CHECKLIST_LOCATION: list[dict[str, Any]] = [
    {
        "id": "cin_proprietaire",
        "nom_fr": "Pièce d’identité du propriétaire",
        "nom_ar": "بطاقة التعريف الوطنية لمالك العقار (أو جواز السفر)",
        "obligatoire": True,
        "categorie": "identite",
        "description_fr": "Copie de la CIN tunisienne ou passeport valide du bailleur.",
        "description_ar": "نسخة من بطاقة التعريف الوطنية التونسية أو جواز سفر ساري المفعول للمؤجر.",
    },
    {
        "id": "cin_locataire",
        "nom_fr": "Pièce d’identité du locataire",
        "nom_ar": "بطاقة التعريف الوطنية للمكتري",
        "obligatoire": True,
        "categorie": "identite",
        "description_fr": "Copie de la CIN du locataire (ou passeport/carte de séjour pour étudiant étranger).",
        "description_ar": "نسخة من بطاقة التعريف الوطنية أو جواز السفر وبطاقة إقامة للطلبة الأجانب.",
    },
    {
        "id": "justificatif_propriete",
        "nom_fr": "Justificatif de propriété ou document établissant le droit de louer",
        "nom_ar": "شهادة ملكية أو وثيقة تثبت صفة المؤجر وحقه في الكراء",
        "obligatoire": True,
        "categorie": "propriete",
        "description_fr": "Certificat de propriété (Titre bleu CPF), contrat d'achat enregistré ou procuration / mandat de gestion.",
        "description_ar": "شهادة ملكية رسمية من إدارة الملكية العقارية أو عقد شراء مسجل أو توكيل رسمي في حالة النيابة.",
    },
    {
        "id": "contrat_location",
        "nom_fr": "Contrat de location avec les informations des deux parties",
        "nom_ar": "عقد كراء محرر بوضوح يتضمن بيانات الطرفين",
        "obligatoire": True,
        "categorie": "contrat",
        "description_fr": "Contrat de bail conforme au Code des Obligations et des Contrats (COC) tunisien.",
        "description_ar": "عقد كراء مطابق لمجلة الالتزامات والعقود التونسية يحدد هوية المكتري والمؤجر.",
    },
    {
        "id": "description_bien",
        "nom_fr": "Adresse et description du bien immobilier",
        "nom_ar": "عنوان العقار ووصفه الدقيق",
        "obligatoire": True,
        "categorie": "bien",
        "description_fr": "Adresse complète, superficie, étage, nombre de pièces et destination (habitation privée).",
        "description_ar": "العنوان الكامل، المساحة، الطابق، عدد الغرف والتخصيص (للسكنى).",
    },
    {
        "id": "loyer_et_caution",
        "nom_fr": "Montant du loyer, caution éventuelle et modalités de paiement",
        "nom_ar": "معين الكراء ومبلغ الضمان المالي وطريقة الخلاص",
        "obligatoire": True,
        "categorie": "financier",
        "description_fr": "Montant mensuel en dinars tunisiens (TND), date d'exigibilité et caution de garantie (1 à 2 mois).",
        "description_ar": "المبلغ الشهري بالدينار التونسي، تاريخ الدفع، ومبلغ الضمان (عادة شهر أو شهرين).",
    },
    {
        "id": "duree_bail",
        "nom_fr": "Durée du bail et conditions de résiliation",
        "nom_ar": "مدة الكراء وشروط الفسخ أو التجديد",
        "obligatoire": True,
        "categorie": "contrat",
        "description_fr": "Période de location (généralement 1 an renouvelable) et préavis de résiliation (1 à 3 mois).",
        "description_ar": "مدة التسويغ (سنة قابلة للتجديد عادة) وأجل الإعلام المسبق بالخروج (شهر إلى 3 أشهر).",
    },
    {
        "id": "etat_des_lieux",
        "nom_fr": "État des lieux et inventaire, si applicable",
        "nom_ar": "محضر معاينة وجرد الأثاث والمعدات (إن وجد)",
        "obligatoire": False,
        "categorie": "bien",
        "description_fr": "Document contradictoire dressé à l'entrée et à la sortie (indispensable pour les meublés et colocations étudiantes).",
        "description_ar": "وثيقة معاينة حالة المحل وجرد التجهيزات عند الدخول والخروج لتفادي النزاع حول الضمان.",
    },
    {
        "id": "signatures_legalisation",
        "nom_fr": "Signatures et formalités requises selon le cas",
        "nom_ar": "التعريف بالإمضاء بالبلدية والتسجيل بالقباضة المالية",
        "obligatoire": True,
        "categorie": "formalites",
        "description_fr": "Légalisation obligatoire des signatures à la municipalité (Baladiya) et enregistrement à la Recette des Finances sous 60 jours.",
        "description_ar": "التعريف بإمضاء الطرفين وجوباً ببلدية تونسية، وتسجيل العقد بالقباضة المالية في أجل 60 يوماً.",
    },
]

CHECKLIST_VENTE: list[dict[str, Any]] = [
    {
        "id": "cin_vendeur",
        "nom_fr": "Pièce d’identité du vendeur",
        "nom_ar": "بطاقة التعريف الوطنية للبائع (أو الوكيل القانوني)",
        "obligatoire": True,
        "categorie": "identite",
        "description_fr": "CIN tunisienne valide ou passeport (avec procuration notariée si vente par procuration).",
        "description_ar": "بطاقة تعريف سارية المفعول (مع توكيل رسمي معرف بالإمضاء إذا كان البيع بنيابة).",
    },
    {
        "id": "cin_acheteur",
        "nom_fr": "Pièce d’identité de l’acheteur",
        "nom_ar": "بطاقة التعريف الوطنية للمشتري",
        "obligatoire": True,
        "categorie": "identite",
        "description_fr": "CIN ou passeport (autorisation préalable du Gouverneur requise pour les acheteurs étrangers).",
        "description_ar": "بطاقة تعريف المشتري (مع وجوب رخصة الوالي المسبقة إذا كان المشتري أجنبياً).",
    },
    {
        "id": "titre_propriete",
        "nom_fr": "Titre de propriété ou justificatif officiel de propriété",
        "nom_ar": "شهادة ملكية رسمية من إدارة الملكية العقارية (رسم عقاري - Titre Bleu)",
        "obligatoire": True,
        "categorie": "propriete",
        "description_fr": "Certificat de propriété récent délivré par la Conservation de la Propriété Foncière (CPF).",
        "description_ar": "شهادة ملكية حديثة مستخرجة من إدارة الملكية العقارية تثبت اسم المالك وعدم وجود موانع.",
    },
    {
        "id": "references_cadastrales",
        "nom_fr": "Informations cadastrales ou références foncières, selon le bien",
        "nom_ar": "المراجع العقارية والمسح العقاري (أرقام الرسم والقطعة)",
        "obligatoire": True,
        "categorie": "propriete",
        "description_fr": "Numéro du titre foncier, numéro de la parcelle, plan cadastral établi par l'Office de la Topographie et du Cadastre (OTC).",
        "description_ar": "عدد الرسم العقاري، القطعة، ومثال هندسي مصادق عليه من ديوان قيس الأراضي ورسم الخرائط.",
    },
    {
        "id": "certificat_non_hypotheque",
        "nom_fr": "Documents relatifs aux éventuelles hypothèques ou charges, si applicables",
        "nom_ar": "شهادة في عدم التحمل والارتفاق (خلو العقار من الرهون أو العقل)",
        "obligatoire": True,
        "categorie": "juridique",
        "description_fr": "Certificat de non-charge ou mainlevée d'hypothèque si le bien avait fait l'objet d'un prêt bancaire.",
        "description_ar": "شهادة تثبت خلو العقار من الرهون البنكية أو الديون، أو الإدلاء بكتب رفع اليد رسمي.",
    },
    {
        "id": "description_bien_vente",
        "nom_fr": "Description du bien : adresse, superficie et caractéristiques",
        "nom_ar": "بيان أوصاف العقار : العنوان، المساحة، والمرافق",
        "obligatoire": True,
        "categorie": "bien",
        "description_fr": "Adresse exacte, superficie couverte et totale, dépendances (parking, cellier) et quote-part de copropriété.",
        "description_ar": "العنوان بدقة، المساحة المغطاة والجملية، التوابع (مأوى سيارة) والنصيب المشاع في الملكية المشتركة.",
    },
    {
        "id": "urbanisme_permis",
        "nom_fr": "Documents d’urbanisme ou autorisations, si nécessaires",
        "nom_ar": "رخصة البناء وشهادة المطابقة أو تقسيم بلدي",
        "obligatoire": False,
        "categorie": "technique",
        "description_fr": "Permis de bâtir, certificat de conformité (chahadat moutabaqa) et plan d'architecte pour les constructions récentes.",
        "description_ar": "رخصة البناء وشهادة المطابقة الفنية للتراتيب العمرانية البلدية.",
    },
    {
        "id": "acte_redige_habilite",
        "nom_fr": "Projet de contrat ou acte de vente préparé selon les formalités applicables",
        "nom_ar": "عقد بيع محرر وجوباً من طرف محامٍ لدى التعقيب أو عدل إشهاد أو محرر بالملكية العقارية",
        "obligatoire": True,
        "categorie": "juridique",
        "description_fr": "Obligation légale (Art. 377 bis Code des Droits Réels) : rédaction par un avocat à la Cour de Cassation, notaire (adoul) ou rédacteur CPF.",
        "description_ar": "شرط جوهري بصريح الفصل 377 مكرر من مجلة الحقوق العينية : التحرير من طرف محام غير متمرن لدى التعقيب أو عدول إشهاد.",
    },
    {
        "id": "quitus_fiscal_et_paiement",
        "nom_fr": "Justificatifs de paiement et formalités fiscales, selon le dossier",
        "nom_ar": "شهادة خلاص الأداء البلدي (الزبلة والخروبة) ووصولات القباضة المالية",
        "obligatoire": True,
        "categorie": "fiscal",
        "description_fr": "Quitus fiscal municipal (taxe sur les immeubles bâtis - TIB), paiement des droits d'enregistrement et taxe de mutation.",
        "description_ar": "إبراء ذمة من البلدية (معلوم العقارات المبنية)، ووصول خلاص معاليم التسجيل ونقل الملكية بالقباضة المالية.",
    },
    {
        "id": "documents_supplementaires",
        "nom_fr": "Documents supplémentaires demandés par le professionnel chargé de la vente",
        "nom_ar": "وثائق تكميلية يطلبها محرر العقد حسب طبيعة العقار",
        "obligatoire": False,
        "categorie": "complement",
        "description_fr": "Attestation de syndic de copropriété (non-dette), procès-verbal d'assemblée générale ou autorisations spécifiques.",
        "description_ar": "شهادة تبرئة ذمة من مأمور اتحاد المالكين (السانبيك) أو إذن قضائي في حالة القصر أو الورثة.",
    },
]


def obtenir_checklist(transaction: str) -> list[dict[str, Any]]:
    """Retourne la checklist configurée selon le type de transaction.

    Args:
        transaction: 'location' ou 'vente'.

    Returns:
        list[dict[str, Any]]: Liste des éléments de la checklist.
    """
    transaction_norm = transaction.strip().lower()
    if transaction_norm == "vente":
        return CHECKLIST_VENTE
    return CHECKLIST_LOCATION


def auditer_dossier(
    transaction: str,
    elements_fournis: list[str] | None = None,
    langue: str = "fr",
) -> dict[str, Any]:
    """Compare une liste d'éléments fournis avec la checklist de référence.

    Args:
        transaction: 'location' ou 'vente'.
        elements_fournis: Identifiants ou noms des pièces déjà réunies.
        langue: 'fr' ou 'ar'.

    Returns:
        dict[str, Any]: Statut d'avancement, éléments présents, manquants et étapes.
    """
    checklist = obtenir_checklist(transaction)
    total = len(checklist)
    fournis_set = set(e.strip().lower() for e in (elements_fournis or []))

    presents: list[dict[str, Any]] = []
    manquants: list[dict[str, Any]] = []
    a_verifier: list[dict[str, Any]] = []

    for item in checklist:
        nom = item["nom_ar"] if langue == "ar" else item["nom_fr"]
        item_id = item["id"].lower()
        description = item["description_ar"] if langue == "ar" else item["description_fr"]

        # Correspondance par ID ou par nom
        est_present = (
            item_id in fournis_set
            or item["nom_fr"].lower() in fournis_set
            or item["nom_ar"].lower() in fournis_set
        )

        detail = {
            "id": item["id"],
            "nom": nom,
            "obligatoire": item["obligatoire"],
            "description": description,
        }

        if est_present:
            presents.append(detail)
        elif item["obligatoire"]:
            manquants.append(detail)
        else:
            a_verifier.append(detail)

    nb_verifies = len(presents)
    score_texte = (
        f"{nb_verifies} sur {total} éléments vérifiés dans cette checklist."
        if langue == "fr"
        else f"{nb_verifies} من أصل {total} وثائق تم التحقق منها في هذه القائمة."
    )

    return {
        "transaction": transaction,
        "total_elements": total,
        "nb_verifies": nb_verifies,
        "pourcentage": round((nb_verifies / total) * 100) if total else 0,
        "score_texte": score_texte,
        "presents": presents,
        "manquants": manquants,
        "a_verifier": a_verifier,
        "complet": nb_verifies == total,
    }
