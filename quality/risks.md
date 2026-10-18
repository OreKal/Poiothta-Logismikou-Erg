# Risk Register

| ID | Κίνδυνος («Αν …, τότε …») | Πηγή | Π | Ε | Προτεραιότητα | Αντιμετώπιση | Χαρακτηριστικό ISO 25010 |
|---|---|---|---|---|---|---|---|
| **R-01** | **Αν** δεχθεί χιλιάδες αιτήματα εξεταστικής (400 users), **τότε** θα καταρρεύσει η 4GB VM (Υ5). | Σ9, Π8, Υ5 | Υ | Υ | Κρίσιμη | Δοκιμές φόρτου & Queue system | Performance efficiency |
| **R-02** | **Αν** 2 φοιτητές πατήσουν κράτηση ταυτόχρονα, **τότε** διπλοκράτηση. | Υ1 | Μ | Υ | Υψηλή | Concurrency testing (DB locks) | Reliability |
| **R-03** | **Αν** το ρολόι του server ώρας έχει άλλο timezone, **τότε** check-in failed. | Σ5 | Χ | Υ | Μέτρια | Ορισμός UTC | Functional suitability |
| **R-04** | **Αν** φωτογραφίσουν το QR code (απομακρυσμένο checkin), **τότε** άδεια αίθουσα. | Υ4, Σ5 | Υ | Μ | Υψηλή | Δυναμικά QR 30s (NFR-06) | Security (Integrity) |
| **R-05** | **Αν** το SSO πέσει, **τότε** κανείς δεν θα μπορεί να κάνει check-in. | Σ11, Π10 | Μ | Υ | Υψηλή | Fallback sessions (NFR-05) | Reliability (Availability) |
| **R-06** | **Αν** η διεπαφή δεν είναι mobile-friendly, **τότε** χαμένα 15λεπτα. | Σ9, Υ1 | Υ | Μ | Υψηλή | NFR-07, Responsive UI | Interaction (Operability) |
| **R-07** | **Αν** πέσει το δίκτυο στο 3ο check-in, **τότε** άδικο ban 7 ημερών. | Σ6, Δ3 | Μ | Μ | Μέτρια | Χειροκίνητο check-in | Functional suitability |
| **R-08** | **Αν** διαρρεύσει η βάση, **τότε** GDPR πρόστιμα. | Σ10 | Χ | Υ | Μέτρια | NFR-02 (Ανωνυμοποίηση) | Security (Confidentiality) |
| **R-11** | **Αν** το σύστημα "κολλήσει" τη Δευτέρα 08:00 λόγω 400 χρηστών. | Π8, Π9 | Υ | Υ | Κρίσιμη | Load testing | Performance efficiency |
| **R-13** | **Αν** δηλωθούν fake μέλη στην αίθουσα (6), **τότε** σπατάλη χώρου. | Π5, Δ4 | Υ | Μ | Μέτρια | Μειώθηκε. (Ο χρόνος χρεώνεται στον creator Δ4) | Functional suitability |
| **R-14** | **Αν** υπάλληλος δει τη λίστα δικαιούχων, **τότε** διαρροή ιατρικών δεδομένων. | Υ3 | Μ | Υ | Κρίσιμη | FR-12 (Απόκρυψη από UI) | Security (Confidentiality) |
| **R-15** | **Αν** η εφαρμογή δεν περνάει τα tests προσβασιμότητας. | Υ2 | Υ | Μ | Υψηλή | NFR-08 (WCAG 2.1 AA checks) | Interaction (Accessibility) |
| **R-16** | **Αν** τα logs περιέχουν PII/passwords, **τότε** παραβίαση ασφάλειας IT. | Υ7 | Μ | Υ | Υψηλή | NFR-10, Log Sanitization | Security (Accountability) |
| **R-17** | **Αν** αλλάξει ημερομηνία εξεταστικής & αργήσει το API. | Υ10 | Μ | Μ | Μέτρια | FR-16 (Admin manual sync) | Compatibility (Interoperability)|