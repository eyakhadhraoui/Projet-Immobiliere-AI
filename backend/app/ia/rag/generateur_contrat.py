"""Générateur de projet de contrat de bail et promesse de vente conforme au droit tunisien."""

from __future__ import annotations

from datetime import date
from typing import Any


def generer_projet_bail(
    bailleur: dict[str, Any],
    locataire: dict[str, Any],
    bien: dict[str, Any],
    conditions: dict[str, Any],
    langue: str = "fr",
) -> str:
    """Génère un projet de contrat de location d'habitation conforme au COC tunisien.

    Args:
        bailleur: Informations sur le bailleur (nom, prenom, cin, adresse).
        locataire: Informations sur le locataire (nom, prenom, cin, qualite, garant).
        bien: Informations sur le bien (type_bien, adresse, ville, surface, nb_pieces, meuble).
        conditions: Clauses financières (loyer, caution, duree, date_debut).
        langue: 'fr' ou 'ar'.

    Returns:
        str: Texte intégral du contrat structuré en Markdown.
    """
    date_jour = date.today().strftime("%d/%m/%Y")
    loyer = conditions.get("loyer", "_________")
    caution = conditions.get("caution", str(float(loyer) * 1) if str(loyer).replace(".", "", 1).isdigit() else "_________")
    duree = conditions.get("duree", "une (1) année renouvelable par tacite reconduction")
    date_debut = conditions.get("date_debut", date_jour)

    est_meuble = bien.get("meuble", False)
    garant = locataire.get("garant")

    if langue == "ar":
        return f"""# عقد كراء محل معد للسكنى
**محرر طبقاً لأحكام مجلة الالتزامات والعقود التونسية**

### بين الممضيين أسفله :

**1. الطرف الأول (المؤجر / صاحب العقار) :**
- **الاسم واللقب :** {bailleur.get('nom_complet', bailleur.get('nom', '........................'))}
- **رقم بطاقة التعريف الوطنية :** {bailleur.get('cin', '................')} المسلمة بتونس.
- **العنوان والمقر المختار :** {bailleur.get('adresse', '........................')}, {bailleur.get('ville', 'تونس')}.

**2. الطرف الثاني (المكتري) :**
- **الاسم واللقب :** {locataire.get('nom_complet', locataire.get('nom', '........................'))}
- **رقم بطاقة التعريف الوطنية (أو جواز السفر) :** {locataire.get('cin', '................')}.
- **الصفة :** {locataire.get('qualite', 'طالب / موظف')}.
{f"- **الضامن والكفيل التضامني (الولي) :** {garant.get('nom', '')} (ب.ت.و عدد: {garant.get('cin', '')})" if garant else ""}

---

### الفصل الأول : موضوع التسويغ ومواصفات العقار
يسوغ الطرف الأول للطرف الثاني الذي يقبل منه العقار الكائن بـ :
**العنوان :** {bien.get('adresse', '........................')}, **المدينة :** {bien.get('ville', 'تونس')}.
- **نوع العقار :** {bien.get('type_bien', 'شقة')} ({'مفروشة ومجهزة' if est_meuble else 'غير مفروشة'}).
- **المساحة التقريبية :** {bien.get('surface', '......')} م²، متكون من {bien.get('nb_pieces', '...')} غرف ومرافقه الصحية.
- **التخصيص :** اتفق الطرفان صراحة على تخصيص هذا المحل للسكنى الخاصة فقط، ويحجر إدخال أي تغييرات أو إحالته للغير أو كرائه من الباطن.

### الفصل الثاني : مدة الكراء
أبرم هذا العقد لمدة **{duree}**، تبتدئ سريانها من تاريخ **{date_debut}**.
ويتجدد العقد ضمنياً ما لم ينبه أحد الطرفين على الآخر برغبته في إنهاء الكراء قبل انتهاء الأجل بشهرين (2) عبر رسالة مضمونة الوصول أو تنبيه بواسطة عدل منفذ.

### الفصل الثالث : معين الكراء وطريقة الدفع
حدد معين الكراء الشهري بمبلغ قدره : **{loyer} دينار تونسي (TND)** شهرياً.
يلتزم المكتري بدفع معين الكراء مسبقاً في بحر الأيام الخمسة الأولى من كل شهر، مقابل وصل خلاص يسلمه المؤجر.

### الفصل الرابع : مبلغ الضمان المالي (Caution)
دفع المكتري للمؤجر عند إمضاء هذا العقد مبلغاً قدره : **{caution} دينار تونسي (TND)** كضمان مالي،
يُرد للمكتري عند نهاية مدة التسويغ وتسليم المفاتيح وخلاص كافة فواتير استهلاك الماء والكهرباء (STEG & SONEDE) ومستحقات السانبيك، بعد التأكد من سلامة المحل وتجهيزاته.

### الفصل الخامس : الإجراءات القانونية والجبائية الإلزامية (البلدية والقباضة)
1. **التعريف بالإمضاء :** يلتزم الطرفان وجوباً بالتعريف بإمضائهما على هذا العقد لدى مصالح الحالة المدنية بالبلدية المختصة ترابياً.
2. **التسجيل بالقباضة المالية :** يتعهد الطرفان بتسجيل هذا العقد لدى القباضة المالية في أجل لا يتجاوز ستين (60) يوماً من تاريخ إبرامه ودفع المعاليم الجبائية المستوجبة قانوناً.

حرر في نظيرين أصليين بتونس، في **{date_jour}**.

**إمضاء المؤجر (معرف به بالبلدية)**             **إمضاء المكتري (معرف به بالبلدية)**
"""

    # Version Française conforme
    return f"""# CONTRAT DE BAIL À USAGE D'HABITATION
**Établi sous le régime du Code des Obligations et des Contrats (COC) tunisien**

### ENTRE LES SOUSSIGNÉS :

**1. Le Bailleur (Propriétaire) :**
- **Nom et Prénom :** {bailleur.get('nom_complet', bailleur.get('nom', '................................................'))}
- **CIN N° :** {bailleur.get('cin', '........................')} délivrée en Tunisie.
- **Demeurant à :** {bailleur.get('adresse', '................................................')}, {bailleur.get('ville', 'Tunis')}.

**2. Le Preneur (Locataire) :**
- **Nom et Prénom :** {locataire.get('nom_complet', locataire.get('nom', '................................................'))}
- **CIN N° (ou Passeport) :** {locataire.get('cin', '........................')}.
- **Qualité :** {locataire.get('qualite', 'Locataire / Étudiant(e)')}.
{f"- **Caution solidaire parentale (Garant) :** {garant.get('nom', '')} (CIN N° {garant.get('cin', '')})" if garant else ""}

---

### ARTICLE 1 — DÉSIGNATION DU BIEN LOUÉ
Le Bailleur donne en location à usage exclusif d'habitation bourgeoise au Preneur, qui accepte, les locaux suivants :
- **Adresse :** {bien.get('adresse', '................................................')}, {bien.get('ville', 'Tunis')}.
- **Type de bien :** {bien.get('type_bien', 'Appartement')} ({'meublé avec inventaire annexé' if est_meuble else 'non meublé'}).
- **Superficie approximative :** {bien.get('surface', '......')} m² comprenant {bien.get('nb_pieces', '...')} pièces principales et commodités.
- **Interdiction :** Toute sous-location ou cession du droit au bail est formellement interdite sans accord écrit préalable.

### ARTICLE 2 — DURÉE ET RÉSILIATION
Le présent bail est consenti pour une durée de **{duree}**, prenant effet le **{date_debut}**.
Il est renouvelable par tacite reconduction, sauf congé signifié par lettre recommandée avec accusé de réception ou exploit d'huissier de justice au moins deux (2) mois avant l'échéance.

### ARTICLE 3 — LOYER ET MODALITÉS DE PAIEMENT
Le loyer mensuel est fixé à la somme de : **{loyer} Dinars Tunisiens (TND)**.
Il est payable d'avance entre le 1er et le 5 de chaque mois, contre quittance délivrée par le Bailleur.

### ARTICLE 4 — DÉPÔT DE GARANTIE (CAUTION)
À la signature des présentes, le Preneur verse entre les mains du Bailleur la somme de : **{caution} Dinars Tunisiens (TND)**.
Ce dépôt, non productif d'intérêts, sera intégralement restitué au Preneur en fin de bail, après remise des clés, apurement des factures d'eau (SONEDE), d'électricité (STEG) et de syndic, et déduction faite des réparations locatives justifiées par l'état des lieux.

### ARTICLE 5 — OBLIGATIONS LÉGALES ET ENREGISTREMENT FISCAL
Conformément à la réglementation tunisienne :
1. **Légalisation municipale :** Les parties s'engagent à faire légaliser leurs signatures à la Municipalité (Baladiya - التعريف بالإمضاء).
2. **Recette des Finances :** Le présent contrat doit être enregistré à la Recette des Finances territorialement compétente dans un délai légal de soixante (60) jours à compter de sa signature, aux droits d'enregistrement en vigueur.

Fait à Tunis, le **{date_jour}**, en deux exemplaires originaux.

**Signature du Bailleur (Légalisée Baladiya)**          **Signature du Preneur (Légalisée Baladiya)**
"""


def generer_projet_promesse_vente(
    vendeur: dict[str, Any],
    acheteur: dict[str, Any],
    bien: dict[str, Any],
    conditions: dict[str, Any],
    langue: str = "fr",
) -> str:
    """Génère un projet de promesse de vente synallagmatique (Wa3d bi-bay3) en Tunisie.

    Rappel Art. 377 bis Code des Droits Réels : l'acte définitif doit être rédigé par un
    avocat à la Cour de Cassation, un notaire (adoul) ou un rédacteur de la CPF.

    Args:
        vendeur: Coordonnées du vendeur et titre foncier.
        acheteur: Coordonnées de l'acheteur.
        bien: Caractéristiques, superficie, titre bleu.
        conditions: Prix en TND, acompte, délai de signature définitive.
        langue: 'fr' ou 'ar'.

    Returns:
        str: Texte du projet de promesse de vente.
    """
    date_jour = date.today().strftime("%d/%m/%Y")
    prix = conditions.get("prix", "_________")
    acompte = conditions.get("acompte", str(float(prix) * 0.1) if str(prix).replace(".", "", 1).isdigit() else "_________")

    if langue == "ar":
        return f"""# مشروع وعد بيع عقاري (Promesse de Vente)
**تنبيه قانوني هام (الفصل 377 مكرر من مجلة الحقوق العينية) :**
*يجب أن يحرر عقد البيع النهائي وجوباً من طرف محامٍ مرسم لدى التعقيب أو عدل إشهاد أو محرر بالملكية العقارية (CPF).*

### بين الطرفين :
- **الواعد بالبيع :** {vendeur.get('nom', '................................')} (ب.ت.و عدد: {vendeur.get('cin', '........')})
- **الموعود له بالشراء :** {acheteur.get('nom', '................................')} (ب.ت.و عدد: {acheteur.get('cin', '........')})

---
### 1. موضوع الوعد والعقار :
عقار كائن بـ : {bien.get('adresse', '........................')}, {bien.get('ville', 'تونس')}.
- **المساحة :** {bien.get('surface', '......')} م²، **الرسم العقاري (Titre Bleu) :** {bien.get('titre_foncier', 'عدد ...................... الملكية العقارية')}.
- يقر البائع بأن العقار خالص من أي رهن بنكي أو عقلة توقيفية، مع الإدلاء بشهادة في عدم التحمل والارتفاق.

### 2. الثمن والتسبقة :
اتفق الطرفان على ثمن بيع جملي قدره : **{prix} دينار تونسي (TND)**.
دفع المشتري تسبقة على الحساب قدرها : **{acompte} دينار تونسي (TND)** تودع كضمان.

### 3. إبراء الذمة البلدية والتسجيل :
يلتزم البائع بالإدلاء بشهادة إبراء ذمة بلدية من معلوم العقارات المبنية (الزبلة والخروبة) قبل إبرام العقد النهائي لدى الأستاذ المحامي أو عدل الإشهاد.

حرر بتونس، في {date_jour}.
"""

    return f"""# PROJET DE PROMESSE DE VENTE IMMOBILIÈRE (TUNISIE)
**Avertissement légal : Article 377 bis du Code des Droits Réels :**
*L'acte de vente définitif d'un bien immatriculé doit être obligatoirement rédigé par un avocat à la Cour de Cassation, un notaire (adoul) ou un rédacteur agréé de la Conservation Foncière.*

### ENTRE LES PARTIES :
- **Le Promettant (Vendeur) :** {vendeur.get('nom', '................................')} (CIN N° {vendeur.get('cin', '........')})
- **Le Bénéficiaire (Acquéreur) :** {acheteur.get('nom', '................................')} (CIN N° {acheteur.get('cin', '........')})

---
### ARTICLE 1 — BIEN IMMOBILIER ET TITRE FONCIER
Bien situé à : {bien.get('adresse', '........................')}, {bien.get('ville', 'Tunis')}.
- **Superficie :** {bien.get('surface', '......')} m² environ.
- **Titre Foncier (Titre Bleu CPF) :** N° {bien.get('titre_foncier', '........................')} délivré par la Conservation Foncière.
- Le vendeur certifie que le bien est libre de toute hypothèque, charge ou saisie.

### ARTICLE 2 — PRIX ET ACOMPTE
Le prix de vente définitif est fixé à : **{prix} Dinars Tunisiens (TND)**.
Il est versé ce jour un acompte de réservation de : **{acompte} Dinars Tunisiens (TND)**.

### ARTICLE 3 — QUITUS FISCAL ET FORMALITÉS
Le vendeur s'engage à fournir le quitus fiscal municipal attestant du paiement de la taxe sur les immeubles bâtis (TIB / Zebla w Khrouba). L'acte définitif sera dressé par le professionnel habilité et soumis à l'enregistrement fiscal et à l'inscription à la CPF.

Fait à Tunis, le {date_jour}.
"""
