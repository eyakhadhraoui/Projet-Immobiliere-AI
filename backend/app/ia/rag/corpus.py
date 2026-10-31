"""Corpus juridique et documentaire de référence pour l'immobilier en Tunisie.

Ce module contient les textes de référence, les obligations légales et les démarches
administratives en Tunisie pour la location et la vente, rédigés en français et en arabe.
"""

from __future__ import annotations

from typing import Any

DOCUMENTS_CORPUS: list[dict[str, Any]] = [
    {
        "id": "loc_base_loi",
        "theme": "location",
        "titre_fr": "Cadre juridique du bail d'habitation en Tunisie (Code des Obligations et des Contrats)",
        "titre_ar": "الإطار القانوني لعقد الكراء السكني في تونس (مجلة الالتزامات والعقود)",
        "source": "Code des Obligations et des Contrats (COC tunisien) - Articles 726 et suivants",
        "tags": ["bail", "contrat", "loi", "location", "parties", "durée", "كراء", "عقد", "قانون"],
        "contenu_fr": (
            "En droit tunisien, le contrat de bail d'habitation est régi par le Code des Obligations et des Contrats (COC). "
            "Le contrat doit être rédigé par écrit et identifier précisément le bailleur (propriétaire ou mandataire) et le preneur (locataire). "
            "Il doit mentionner l'adresse exacte du bien, son affectation exclusive à l'habitation, le montant du loyer mensuel en dinars tunisiens (TND), "
            "la périodicité de paiement, la durée de la location (généralement 1 an renouvelable par tacite reconduction) et les modalités de résiliation. "
            "Le préavis de résiliation doit être notifié par lettre recommandée avec accusé de réception ou acte d'huissier de justice (huissier notaire), généralement 1 à 3 mois avant le terme."
        ),
        "contenu_ar": (
            "يخضع عقد كراء المحلات السكنية في تونس لأحكام مجلة الالتزامات والعقود (الفصول 726 وما بعده). "
            "يجب تحرير عقد الكراء كتابة وتحديد هوية المؤجر والمكتري بدقة. يتضمن العقد وجوباً عنوان المحل المعد للسكنى، "
            "معين الكراء الشهري بالدينار التونسي، تاريخ الاستحقاق، مدة الكراء (سنة قابلة للتجديد ضمنياً في العادة)، "
            "وشروط الفسخ أو التنبيه بالخروج، والذي يتم عبر رسالة مضمونة الوصول مع الإعلام بالبلوغ أو عن طريق عدل منفذ قبل انتهاء المدة بشهر إلى 3 أشهر."
        ),
    },
    {
        "id": "loc_formalites_baladiya_qabadha",
        "theme": "location",
        "titre_fr": "Formalités obligatoires : Légalisation municipale et Recette des Finances",
        "titre_ar": "الإجراءات الإلزامية : التعريف بالإمضاء بالبلدية والتسجيل بالقباضة المالية",
        "source": "Municipalités tunisiennes et Code de l'Enregistrement et du Timbre Fiscal",
        "tags": ["baladiya", "municipalité", "recette des finances", "légalisation", "signature", "قباضة", "بلدية", "تعريف بالإمضاء"],
        "contenu_fr": (
            "Deux formalités administratives sont incontournables en Tunisie pour rendre le bail valide et opposable :\n"
            "1. Légalisation de signature à la Municipalité (Baladiya - التعريف بالإمضاء) : Bailleur et locataire doivent obligatoirement faire légaliser leurs signatures munis de leurs pièces d'identité (CIN ou passeport valide). Cette formalité est exigée par la STEG et la SONEDE pour l'ouverture des compteurs.\n"
            "2. Enregistrement à la Recette des Finances (القباضة المالية) : L'enregistrement du contrat de location doit être effectué dans un délai légal de 60 jours à compter de sa signature. Le droit d'enregistrement standard s'élève à 1 % du montant cumulé des loyers sur la durée du bail, augmenté du droit de timbre fiscal."
        ),
        "contenu_ar": (
            "يتطلب عقد الكراء في تونس إتمام إجراءين أساسيين لإكسابه القوة القانونية والتاريخ الثابت :\n"
            "1. التعريف بالإمضاء في البلدية (Légalisation) : يلتزم المؤجر والمكتري بالتعريف بإمضائهما لدى مصالح الحالة المدنية بأي بلدية تونسية مع الاستظهار ببطاقة التعريف الوطنية أو جواز السفر. وهو وثيقة ضرورية للربط بشبكتي الكهرباء (STEG) والماء (SONEDE).\n"
            "2. التسجيل بالقباضة المالية : يوجب القانون تسجيل عقد الكراء لدى القباضة المالية مرجع النظر الترابي في أجل أقصاه 60 يوماً من تاريخ التوقيع. وتبلغ معلوم التسجيل 1 % من القيمة الجملية للكراء لكامل المدة، مع إضافة معاليم الطابع الجبائي."
        ),
    },
    {
        "id": "loc_etudiants",
        "theme": "location",
        "titre_fr": "Dossier spécifique pour les étudiants (caution solidaire parentale et colocation)",
        "titre_ar": "الملف الخاص بالطلبة (الضمان التضامني للوالدين والكراء المشترك)",
        "source": "Pratiques professionnelles immobilières et droit civil tunisien",
        "tags": ["etudiant", "étudiants", "caution", "garant", "colocation", "université", "طالب", "طلبة", "ضامن", "كراء مشترك"],
        "contenu_fr": (
            "Pour les étudiants cherchant à louer un logement en Tunisie (studio, appartement ou colocation), les propriétaires exigent généralement :\n"
            "- Pièce d'identité de l'étudiant (CIN) et carte d'étudiant ou attestation d'inscription universitaire en cours.\n"
            "- Engagement de caution solidaire parentale (كفالة تضامنية) : lettre d'engagement signée et légalisée par le père, la mère ou le tuteur légal, garantissant le paiement des loyers en cas de défaillance.\n"
            "- Justificatif de revenus du garant : copie de la fiche de paie récente, déclaration d'impôt ou extrait de compte bancaire.\n"
            "- En cas de colocation étudiante, il est fortement conseillé d'inscrire le nom de tous les colocataires sur le contrat avec mention de la clause de solidarité, ou de conclure des baux séparés par chambre."
        ),
        "contenu_ar": (
            "بالنسبة للطلبة الراغبين في تسويغ مسكن أو استوديو أو الكراء المشترك (colocation) في تونس، يطلب أصحاب العقارات الوثائق التالية :\n"
            "- بطاقة التعريف الوطنية للطالب وبطاقة الطالب أو شهادة التسجيل الجامعي للسنة الحالية.\n"
            "- التزام كفيل ضامن (كفالة تضامنية من الولي) : التزام كتابي معرف بالإمضاء من الأب أو الأم أو الضامن يلتزم بموجبه بخلاص معينات الكراء عند الاقتضاء.\n"
            "- وثيقة تثبت دخل الضامن : شهادة عمل أو كشف حساب بنكي أو بيان جراية.\n"
            "- في حالة الكراء الجماعي للطلبة، يُستحسن ذكر أسماء كافة المقيمين في العقد أو إبرام عقود منفردة لكل غرفة."
        ),
    },
    {
        "id": "loc_caution_garantie",
        "theme": "location",
        "titre_fr": "Dépôt de garantie (caution) et état des lieux contradictoire",
        "titre_ar": "مبلغ الضمان المالي (الكمبيالة / Caution) ومحضر جرد المعاينة",
        "source": "Usage immobilier tunisien et Code des Obligations et des Contrats",
        "tags": ["caution", "garantie", "dépôt", "inventaire", "état des lieux", "ضمان", "جرد", "معاينة"],
        "contenu_fr": (
            "La caution de garantie (dépôt de garantie) est versée au propriétaire lors de la remise des clés. "
            "En Tunisie, son montant équivaut couramment à 1 ou 2 mois de loyer. Elle sert à couvrir d'éventuelles dégradations ou des factures impayées (STEG, SONEDE, syndic). "
            "Elle doit être restituée au locataire dans son intégralité à la fin du bail, après remise des clés et déduction faite des frais de remise en état justifiés. "
            "L'état des lieux d'entrée et de sortie (établi contradictoirement et annexé au contrat) est la meilleure protection pour récupérer sa caution sans litige."
        ),
        "contenu_ar": (
            "مبلغ الضمان (Caution) يُدفع للمؤجر عند استلام المفاتيح. في تونس، يعادل هذا المبلغ عادة كراء شهر أو شهرين. "
            "يهدف الضمان إلى تغطية أي أضرار قد تلحق بالعين المؤجرة أو خلاص فواتير الكهرباء والماء ومستحقات السانبيك المتخلدة بالذمة. "
            "يُسترجع مبلغ الضمان كاملاً للمكتري عند مغادرة المحل وتسليم المفاتيح وإجراء المعاينة. "
            "ويعتبر محضر المعاينة وجرد الأثاث (عند الدخول وعند الخروج) الضمانة المثلى لتفادي أي خلاف واسترجاع كامل مبلغ الضمان."
        ),
    },
    {
        "id": "vente_redaction_avocat",
        "theme": "vente",
        "titre_fr": "Obligation de rédaction de l'acte de vente par un professionnel habilité (Art. 377 bis)",
        "titre_ar": "وجوبية تحرير عقد البيع من طرف محامٍ أو عدل إشهاد أو محرر CPF (الفصل 377 مكرر)",
        "source": "Code des Droits Réels tunisien - Article 377 bis",
        "tags": ["avocat", "adoul", "notaire", "rédaction", "vente", "377 bis", "محام", "عدل إشهاد", "عقد بيع", "حقوق عينية"],
        "contenu_fr": (
            "En Tunisie, la vente d'un bien immobilier immatriculé au registre foncier est soumise à une règle d'ordre public fondamentale :\n"
            "Selon l'article 377 bis du Code des Droits Réels, l'acte de vente doit obligatoirement être rédigé par :\n"
            "1. Un avocat non stagiaire admis à exercer devant la Cour de Cassation ;\n"
            "2. Un notaire (عدل إشهاد - adoul) ;\n"
            "3. Ou un rédacteur agréé de la Conservation de la Propriété Foncière (CPF).\n"
            "Tout acte de vente rédigé sous seing privé (entre particuliers) ou par une personne non habilitée est frappé de nullité absolue et ne pourra jamais être inscrit sur le Titre Foncier."
        ),
        "contenu_ar": (
            "في تونس، يخضع بيع العقارات المسجلة لشرط شكلي جوهري من النظام العام بمقتضى الفصل 377 مكرر من مجلة الحقوق العينية :\n"
            "يجب وجوباً أن يُحرر عقد البيع العقاري من قبل إحدى الجهات التالية فقط :\n"
            "1. محامٍ مباشر غير متمرن مرسم لدى التعقيب ؛\n"
            "2. عدل إشهاد (Notaire) ؛\n"
            "3. محررو إدارة الملكية العقارية.\n"
            "كل عقد محرر بكتب خطي اليد بين الخواص أو من غير هؤلاء المحررين يعد باطلاً بطلاناً مطلقاً ولا يمكن ترسيمه بالرسم العقاري."
        ),
    },
    {
        "id": "vente_titre_bleu_cpf",
        "theme": "vente",
        "titre_fr": "Titre de propriété (Titre Bleu) et certificat de non-hypothèque",
        "titre_ar": "الرسم العقاري (Titre Bleu) وشهادة عدم التحمل والارتفاق من الملكية العقارية",
        "source": "Conservation de la Propriété Foncière (CPF - إدارة الملكية العقارية)",
        "tags": ["titre bleu", "cpf", "propriété", "hypothèque", "conservation foncière", "رسم عقاري", "ملكية عقارية", "شهادة عدم إشكال"],
        "contenu_fr": (
            "Avant tout achat immobilier en Tunisie, il est impératif de vérifier la situation foncière du bien auprès de la Conservation de la Propriété Foncière (CPF) :\n"
            "- Certificat de propriété (Titre Bleu - شهادة ملكية) : délivré par la CPF, il atteste de l'identité du propriétaire réel, de la superficie exacte, et liste les servitudes éventuelles.\n"
            "- Certificat de non-hypothèque et de non-charge (شهادة في عدم التحمل والارتفاق) : atteste que l'immeuble n'est pas grevé d'une hypothèque bancaire, d'une saisie conservatoire ou d'un privilège du Trésor.\n"
            "- S'il y a eu un prêt bancaire antérieur, le vendeur doit fournir une mainlevée d'hypothèque (كتب رفع يد) en bonne et due forme."
        ),
        "contenu_ar": (
            "قبل إتمام أي عملية شراء عقاري في تونس، من الضروري جداً التثبت من الوضعية القانونية للعقار لدى إدارة الملكية العقارية (CPF) :\n"
            "- شهادة ملكية حديثة (Titre Bleu) : تثبت اسم المالك الفعلي، مساحة العقار المحددة، وأي حقوق ارتفاق.\n"
            "- شهادة في عدم التحمل والارتفاق (خلو من الرهون) : تثبت أن العقار خالص من أي رهن بنكي أو عقلة توقيفية أو ديون لفائدة الخزينة العامة.\n"
            "- في حال وجود قرض سابق، يجب على البائع الإدلاء بكتب رفع يد رسمي ومصادق عليه صادر عن البنك الدائن."
        ),
    },
    {
        "id": "vente_fiscalite_quitus",
        "theme": "vente",
        "titre_fr": "Fiscalité de la vente : Quitus municipal (Zebla w Khrouba) et Recette des Finances",
        "titre_ar": "الجباية العقارية : إبراء الذمة البلدي (الزبلة والخروبة) والتسجيل بالقباضة",
        "source": "Code de la Fiscalité Locale et Recette des Finances de Tunisie",
        "tags": ["fiscalité", "quitus", "municipalité", "recette", "zebla", "khrouba", "taxe", "قباضة", "بلدية", "زبلة وخروبة", "معلوم"],
        "contenu_fr": (
            "Les obligations fiscales liées à la vente immobilière en Tunisie comprennent :\n"
            "1. Le quitus fiscal municipal (شهادة إبراء ذمة / خلاص معلوم العقارات المبنية - Zebla w Khrouba) : Le vendeur doit fournir une quittance délivrée par la municipalité attestant du paiement de la taxe sur les immeubles bâtis (TIB) pour les années échues.\n"
            "2. Droits d'enregistrement à la Recette des Finances : L'acte de vente doit être enregistré dans les 60 jours suivant sa signature. Les droits de mutation et taxes d'enregistrement sont calculés selon le barème en vigueur (droits proportionnels et timbre).\n"
            "3. L'inscription définitive à la Conservation de la Propriété Foncière (CPF) : Après enregistrement à la recette, le dossier est déposé à la CPF pour inscrire le nouvel acquéreur sur le titre foncier et émettre son certificat de propriété."
        ),
        "contenu_ar": (
            "المتطلبات الجبائية لبيع عقار في تونس تشمل :\n"
            "1. شهادة خلاص الأداء البلدي (شهادة إبراء ذمة - الزبلة والخروبة) : يقدم البائع وصلاً بلدياً يثبت خلاص معلوم العقارات المبنية والأراضي غير المبنية للسنوات المستوجبة.\n"
            "2. معاليم التسجيل بالقباضة المالية : يتم تسجيل عقد البيع وجوباً بالقباضة المالية في أجل 60 يوماً من إمضائه، وتُدفع معاليم نقل الملكية والضرائب المستوجبة قانوناً.\n"
            "3. الترسيم النهائي بإدارة الملكية العقارية : بعد التسجيل الجبائي، يُودع الملف بالملكية العقارية لإدراج اسم المشتري رسمياً على الرسم العقاري واستخراج شهادة ملكيته."
        ),
    },
    {
        "id": "vente_acheteurs_etrangers",
        "theme": "vente",
        "titre_fr": "Acquisition immobilière par les étrangers en Tunisie (Autorisation du Gouverneur)",
        "titre_ar": "شراء العقارات من طرف الأجانب في تونس (رخصة الوالي)",
        "source": "Législation tunisienne sur les transactions immobilières des étrangers",
        "tags": ["étranger", "gouverneur", "autorisation", "wali", "أجنبي", "رخصة الوالي", "والي"],
        "contenu_fr": (
            "Pour les acheteurs de nationalité étrangère souhaitant acheter un bien immobilier en Tunisie :\n"
            "- L'autorisation préalable du Gouverneur territorialement compétent (رخصة الوالي - Rokhset al-Wali) est obligatoire avant la signature de l'acte de vente définitif.\n"
            "- La promesse de vente (promesse synallagmatique) est signée sous condition suspensive de l'obtention de cette autorisation.\n"
            "- Le paiement du prix doit être obligatoirement effectué par virement bancaire international en devises convertibles auprès de la Banque Centrale de Tunisie (fiche d'investissement).\n"
            "- Exception : les ressortissants de certains pays disposant de conventions bilatérales spécifiques ou pour les biens situés dans des zones de développement touristique précises."
        ),
        "contenu_ar": (
            "بالنسبة للمشترين الأجانب الراغبين في اقتناء عقار سكني بتونس :\n"
            "- الحصول على رخصة الوالي (Autorisation du Gouverneur) مسبقاً هو شرط إلزامي ومفروض قانوناً قبل إبرام عقد البيع النهائي.\n"
            "- يحرر الطرفان وعد بيع (عقد ابتدائي) يتضمن شرطاً تعليقياً متعلقاً بالحصول على موافقة الوالي.\n"
            "- يتم خلاص ثمن البيع وجوباً بتحويل بنكي دولي بالعملة الأجنبية القابلة للتحويل عبر البنك المركزي التونسي واستخراج إشعار استثمار.\n"
            "- يُمنع منعاً باتاً على الأجانب شراء الأراضي الفلاحية في تونس وفق القانون المنظم للأنشطة الفلاحية."
        ),
    },
    {
        "id": "diwan_guide_location",
        "theme": "location",
        "titre_fr": "Guide officiel Diwan : Pièces et démarches pour la location immobilière",
        "titre_ar": "الدليل الإداري الرسمي ديوان : وثائق وإجراءات كراء عقار في تونس",
        "source": "Diwan — Enregistrement d'un contrat de location (https://www.diwan.tn/fr/article/article_location)",
        "tags": ["diwan", "location", "démarches", "enregistrement", "étapes", "ديوان", "كراء", "إجراءات"],
        "contenu_fr": (
            "Démarches officielles et pièces selon le Guide pratique et la fiche Diwan (https://www.diwan.tn/fr/article/article_location) :\n"
            "A. Pièces à préparer :\n"
            "1. Identité des parties : pièce d'identité du propriétaire/bailleur et du locataire ; pour une personne morale, documents de l'entreprise et pouvoir du signataire.\n"
            "2. Droit de louer : titre ou justificatif de propriété, ou document établissant que le bailleur est autorisé à louer le bien.\n"
            "3. Informations sur le bien : adresse complète, description du local et références foncières si utile.\n"
            "4. Contrat de location : identité des parties, adresse, destination/usage, loyer, durée, modalités de paiement, dépôt de garantie éventuel, répartition des charges et conditions de résiliation.\n"
            "5. État des lieux et inventaire : à préparer notamment pour un logement meublé.\n"
            "6. Annexes : documents mentionnés dans le contrat ou convenus.\n"
            "7. Justificatifs fiscaux et formalités : quittances ou documents demandés pour l'enregistrement.\n"
            "B. Démarches générales en 5 étapes :\n"
            "1. Vérifier l'identité des parties et le droit du bailleur à louer.\n"
            "2. Préparer le contrat et vérifier la cohérence des informations.\n"
            "3. Légaliser les signatures auprès du service municipal compétent (Baladiya).\n"
            "4. Enregistrer à la Recette des finances compétente avec copies du contrat, signatures légalisées et justificatif fiscal.\n"
            "5. Conserver une copie du contrat signé et les reçus délivrés."
        ),
        "contenu_ar": (
            "الإجراءات والوثائق الرسمية حسب الدليل الإداري (ديوان تونس) :\n"
            "أ. الوثائق الواجب إعدادها :\n"
            "1. هوية الأطراف : بطاقة تعريف المالك والمكتري، ووثائق الشركة والتفويض في حال الشخص المعنوي.\n"
            "2. صفة المؤجر : شهادة ملكية أو وثيقة تثبت حق التسويغ.\n"
            "3. بيانات العقار : العنوان الكامل، الوصف والمراجع العقارية.\n"
            "4. عقد الكراء : الهوية، العنوان، التخصيص، معين الكراء، المدة، طريقة الخلاص، مبلغ الضمان، وتوزيع المصاريف.\n"
            "5. محضر المعاينة وجرد الأثاث : خاصة في المحلات المفروشة.\n"
            "6. الملاحق والمؤيدات الجبائية للتسجيل بالقباضة المالية.\n"
            "ب. المراحل الخمس الرئيسية :\n"
            "1. التثبت من هوية الأطراف وحق المؤجر.\n"
            "2. تحرير العقد والتأكد من تطابق البيانات.\n"
            "3. التعريف بالإمضاء وجوباً بالبلدية.\n"
            "4. التسجيل بالقباضة المالية وتقديم النسخ مع وصولات الخلاص.\n"
            "5. الاحتفاظ بنسخ العقد والوصولات الرسمية المسلمة."
        ),
    },
    {
        "id": "diwan_guide_vente",
        "theme": "vente",
        "titre_fr": "Guide officiel Diwan & Portail national : Pièces et démarches pour la vente immobilière",
        "titre_ar": "الدليل الإداري ديوان والبوابة الوطنية للخدمات : وثائق وإجراءات بيع عقار",
        "source": "Diwan — Enregistrement d'un acte d'acquisition (https://www.diwan.tn/fr/article/cession) & Portail national des services administratifs (https://services.gov.tn/affaires-foncieres/)",
        "tags": ["diwan", "vente", "cession", "affaires foncières", "services.gov.tn", "شراء", "بيع", "شؤون عقارية"],
        "contenu_fr": (
            "Démarches officielles et pièces selon le Guide pratique, la fiche Diwan et le portail national des services administratifs :\n"
            "A. Pièces et justificatifs à préparer :\n"
            "1. Identité du vendeur et de l'acheteur (état civil complet).\n"
            "2. Justificatif de propriété : titre foncier, certificat de propriété CPF ou acte d'acquisition admis.\n"
            "3. Références du bien : adresse, désignation, superficie et références foncières/cadastrales.\n"
            "4. Situation juridique : vérifier copropriétaires, indivisions, hypothèques, charges, servitudes ou droits de tiers.\n"
            "5. Projet d'acte de vente : préparé par un professionnel habilité (Art. 377 bis).\n"
            "6. Documents fiscaux et municipaux : quitus taxe municipale (Zebla w Khrouba), quittances requises.\n"
            "7. Procuration ou autorisation : si une partie est représentée ou autorisation préalable nécessaire.\n"
            "8. Pièces complémentaires : documents de société (personne morale), documents liés au crédit hypothécaire.\n"
            "B. Démarches générales en 5 étapes :\n"
            "1. Faire vérifier le titre de propriété et la capacité du vendeur à céder le bien.\n"
            "2. Vérifier les charges, indivisions, hypothèques et procurations.\n"
            "3. Faire préparer l'acte par un professionnel compétent (avocat à la Cour de Cassation, notaire, rédacteur CPF).\n"
            "4. Confirmer auprès de la Recette des finances les documents, copies et droits d'enregistrement applicables.\n"
            "5. Accomplir les formalités foncières auprès de la Conservation de la propriété foncière (CPF) et conserver les reçus et documents enregistrés."
        ),
        "contenu_ar": (
            "الإجراءات والوثائق الرسمية لبيع عقار حسب ديوان والبوابة الوطنية للخدمات الإدارية :\n"
            "أ. الوثائق الواجب إعدادها :\n"
            "1. هوية البائع والمشتري والحالة المدنية.\n"
            "2. إثبات الملكية : رسم عقاري، شهادة ملكية CPF، أو عقد شراء مسجل.\n"
            "3. مراجع العقار ومثاله الهندسي.\n"
            "4. الوضعية القانونية : التثبت من الشركاء في الإرث، الشياع، والرهون والارتفاقات.\n"
            "5. مشروع عقد البيع محرر وجوباً من جهة مختصة ومؤهلة.\n"
            "6. وثائق جبائية وبلدية : إبراء ذمة بلدي ووصولات الخلاص.\n"
            "7. توكيل رسمي أو رخصة خاصة في حال وجود نيابة.\n"
            "ب. المراحل الخمس الرئيسية :\n"
            "1. التثبت من شهادة الملكية وأهلية البائع في التفويت.\n"
            "2. التأكد من خلو العقار من الرهون أو التقييدات.\n"
            "3. تحرير العقد من طرف محام لدى التعقيب أو عدل إشهاد.\n"
            "4. دفع معاليم التسجيل الجبائي بالقباضة المالية.\n"
            "5. إتمام إجراءات الترسيم لدى إدارة الملكية العقارية واستخراج شهادة ملكية المشتري."
        ),
    },
    {
        "id": "guide_verification_pages_contrat",
        "theme": "general",
        "titre_fr": "Conseils pratiques pour vérifier les pages d'un contrat immobilier",
        "titre_ar": "نصائح عملية للتثبت من صفحات عقد الكراء أو البيع العقاري",
        "source": "Guide pratique — Documents nécessaires pour la location et la vente immobilière en Tunisie",
        "tags": ["contrat", "vérification", "pages", "numérotation", "annexes", "illisible", "صفحات", "عقد", "تثبت"],
        "contenu_fr": (
            "Recommandations du Guide pratique pour contrôler les pages d'un contrat ou acte immobilier :\n"
            "1. Comparer le nombre de pages du fichier ou document physique avec la numérotation visible sur les pages (ex. page 1/4, 2/4...).\n"
            "2. Repérer les éventuels sauts de numérotation, les pages blanches/vides ou les pages tronquées/illisibles.\n"
            "3. Vérifier si le contrat fait expressément référence à des annexes (ex. inventaire, plan, procès-verbal) et s'assurer que ces annexes sont effectivement jointes au dossier.\n"
            "4. Ne pas conclure hâtivement qu'une page est juridiquement manquante sur la seule base d'un saut de numéro : demander confirmation à l'émetteur ou au professionnel chargé du dossier.\n"
            "5. Distinguer clairement dans le dossier :\n"
            "   - Une pièce non fournie (absente du dossier),\n"
            "   - Une pièce fournie mais illisible ou incomplète,\n"
            "   - Une pièce dont l'obligation reste à confirmer selon la situation (ex. permis de bâtir, syndic, procuration)."
        ),
        "contenu_ar": (
            "توصيات الدليل العملي لفحص صفحات وملاحق العقد العقاري :\n"
            "1. مقارنة عدد صفحات الوثيقة مع الترقيم المكتوب (مثال: صفحة 1 من 4).\n"
            "2. الانتباه لأي انقطاع في تسلسل الأرقام أو وجود صفحات فارغة أو غير مقروءة.\n"
            "3. التثبت مما إذا كان العقد يشير إلى ملاحق مرفقة (كالمثال الهندسي أو جرد الأثاث) والتأكد من إرفاقها فعلياً.\n"
            "4. عدم الجزم بنقص الصفحة قانوناً بمجرد انقطاع الترقيم، بل التثبت من محرر العقد أو الجهة المصدرة.\n"
            "5. التمييز الواضح بين : وثيقة غير متوفرة إطلاقاً، وثيقة موجودة لكنها غير واضحة، ووثيقة تتطلب التأكيد حسب الحالة (مثل رخصة البناء أو براءة ذمة السانبيك)."
        ),
    },
    {
        "id": "guide_tableau_controle_dossier",
        "theme": "general",
        "titre_fr": "Tableau de contrôle du dossier immobilier (Présent, Manquant, À confirmer, À faire)",
        "titre_ar": "جدول مراقبة الملف العقاري (متوفر، ناقص، قيد التأكيد، قيد الإنجاز)",
        "source": "Guide pratique — Documents nécessaires pour la location et la vente immobilière en Tunisie",
        "tags": ["tableau", "contrôle", "dossier", "statut", "location", "vente", "جدول", "مراقبة", "ملف"],
        "contenu_fr": (
            "Tableau de synthèse du dossier avant signature :\n"
            "1. Identité des parties : Location (À préparer), Vente (À préparer) → État : Présent ou Manquant.\n"
            "2. Justificatif de propriété / droit de louer : Location (À vérifier), Vente (À vérifier) → État : Présent ou Manquant.\n"
            "3. Contrat ou projet d'acte : Location (Contrat de location), Vente (Acte de vente) → État : Présent ou Manquant.\n"
            "4. Description et références du bien : Location (À renseigner), Vente (À renseigner) → État : Présent ou Manquant.\n"
            "5. Pièces fiscales / reçus : Location (Selon formalités), Vente (Selon formalités) → État : Présent ou À confirmer.\n"
            "6. Annexes et documents complémentaires : Location (Selon le contrat), Vente (Selon le dossier) → État : Présent ou À confirmer.\n"
            "7. Signatures, enregistrement et formalités foncières : Location (À vérifier), Vente (À vérifier) → État : Fait ou À faire."
        ),
        "contenu_ar": (
            "جدول مراقبة ومتابعة وثائق الملف قبل إتمام المعاملة :\n"
            "1. هوية الأطراف : كراء (وجب الإعداد)، بيع (وجب الإعداد) ← الحالة : متوفر أو ناقص.\n"
            "2. إثبات الملكية / حق التسويغ : كراء (تثبت)، بيع (تثبت) ← الحالة : متوفر أو ناقص.\n"
            "3. العقد أو المشروع : كراء (عقد كراء)، بيع (عقد بيع) ← الحالة : متوفر أو ناقص.\n"
            "4. وصف وبيانات العقار : كراء (تحديد)، بيع (تحديد) ← الحالة : متوفر أو ناقص.\n"
            "5. وصولات الجباية : كراء (حسب الإجراء)، بيع (حسب الإجراء) ← الحالة : متوفر أو قيد التأكيد.\n"
            "6. الملاحق والوثائق التكميلية : كراء (حسب العقد)، بيع (حسب الملف) ← الحالة : متوفر أو قيد التأكيد.\n"
            "7. الإمضاء، التسجيل بالقباضة والترسيم بالملكية : كراء (تثبت)، بيع (تثبت) ← الحالة : منجز أو قيد الإنجاز."
        ),
    },
]


def obtenir_corpus() -> list[dict[str, Any]]:
    """Retourne la liste complète des articles du corpus juridique tunisien."""
    return DOCUMENTS_CORPUS
