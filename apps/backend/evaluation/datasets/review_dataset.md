# Golden Dataset Comprehensive Review Document

This document presents the complete 30-case golden dataset and the associated ingestion manifest for review.

## 1. Document Ingestion Manifest

| Filename | Document ID | SHA-256 | Page Count | Chunk Count | Upload Status | Embeddings Verified | Evaluation User ID |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Arabic Document 2.pdf | `1ef24635-4f7f-4849-93a7-3a4fc6bf1560` | `0c08c0a585e9...` | 12 | 47 | `ready` | Yes | `dc803d72-f5d6-46e2-82a9-5c32bcda2815` |
| Document 3 Advanced.pdf | `6be74837-9a43-44ff-bba2-eebaeeb10823` | `1739e0672142...` | 17 | 8 | `ready` | Yes | `dc803d72-f5d6-46e2-82a9-5c32bcda2815` |
| English Document 1.pdf | `0d453a69-e504-48c6-bc6c-09e801756218` | `8cfb265fe287...` | 19 | 13 | `ready` | Yes | `dc803d72-f5d6-46e2-82a9-5c32bcda2815` |

## 2. Dataset Distribution Summary

- **Total Cases**: 30
- **Arabic Questions**: 13 (Requirement: >= 8)
- **English Questions**: 17 (Requirement: >= 8)
- **Cross-lingual Questions**: 3

## 3. Test Cases List

---

### Case TC-001

- **Document Filename**: Arabic Document 2.pdf
- **Document ID**: `1ef24635-4f7f-4849-93a7-3a4fc6bf1560`
- **Category**: `direct_factual`
- **Source Language**: `ar`
- **Question Language**: `ar`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > ما هي أنواع الفعالية المذكورة في النص؟
- **Reference Answer**:
  > الفعالية التعليمية، الفعالية التنظيمية، والفعالية الإنتاجية.
- **Required Facts**: ["الفعالية التعليمية", "الفعالية التنظيمية", "الفعالية الإنتاجية"]
- **Reference Page Numbers**: [10]
- **Reference Chunk IDs**: `['432d866e-d0c8-4065-9132-e3310c466f4a']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "ييت بفعاليتهيييا التعليميييية والتنظيميييية واإلنتاجيية وننشيب بالتيالي مؤسسيات ومنظميات تتعاميل ميط يذ التقنيية بضيي . تنتجها وتعلمها وتتدصها 4. ال يكفيي أن ت صيص أي دولية صربيية ..."

---

### Case TC-002

- **Document Filename**: Arabic Document 2.pdf
- **Document ID**: `1ef24635-4f7f-4849-93a7-3a4fc6bf1560`
- **Category**: `direct_factual`
- **Source Language**: `ar`
- **Question Language**: `ar`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > ما هو المجال الذي يذكر النص أنه يواجه صعوبات ومعوقات تعيق استفادته؟
- **Reference Answer**:
  > النص يذكر أن الصعوبات والمعوقات تواجه المجال التعليمي، أي التعليم.
- **Required Facts**: ["الصعوبات والمعوقات التي تواجه الو ط التعليمي", "تعيق استفادة التعليم"]
- **Reference Page Numbers**: [2]
- **Reference Chunk IDs**: `['89d9a844-6fcd-4442-a950-057e775c1873']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "يييا المعلوميات واالتصياالت فيي ال يدمات التعليميية ، وأخييراً الكشيف صين نقياو القيو والضعف في معال التنيية التضتيية لتكنولوجييا المعلوميات واالتصياالت فيي التليدان الناميية لتضدي..."

---

### Case TC-003

- **Document Filename**: Arabic Document 2.pdf
- **Document ID**: `1ef24635-4f7f-4849-93a7-3a4fc6bf1560`
- **Category**: `direct_factual`
- **Source Language**: `ar`
- **Question Language**: `ar`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > ما هما المصطلحان التقنيان المذكوران في النص كأمثلة على التقنيات الحديثة المستخدمة في التعليم؟
- **Reference Answer**:
  > المصطلحان المذكوران هما "Data Base System" و"Artificial intelligence".
- **Required Facts**: ["ذكر مصطلح Data Base System في النص", "ذكر مصطلح Artificial intelligence في النص"]
- **Reference Page Numbers**: [1]
- **Reference Chunk IDs**: `['03c9f2a0-4cd4-451b-9c3d-e209be1310e2']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "اكمر الذي حيدا بيالتربويين إلي تتنيي أنمياو وبيدائل تعليميية مت يو ، وتيوفير بيئة تفاصلية وحيويية صلي د جية صاليية مين المرونية والكفيا ؛ لشيد انتتيا الميتعل وتجذبه إليها . في وي ر..."

---

### Case TC-004

- **Document Filename**: Arabic Document 2.pdf
- **Document ID**: `1ef24635-4f7f-4849-93a7-3a4fc6bf1560`
- **Category**: `explanation`
- **Source Language**: `ar`
- **Question Language**: `ar`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > لماذا يعتبر التركيز على الجانب التقني ضرورياً وفقاً للنص؟
- **Reference Answer**:
  > النص يوضح أن مجرد توفر موارد دولية أو مالية لا يكفي لتجهيز البرمجيات أو المعدات، فإذا لم يُركز الجهد على التنمية التقنية فإن هذه الموارد لن تُستَغل بفعالية. لذلك يشدد النص على ضرورة التركيز على الجانب التقني لتحقيق التنمية التقنية المطلوبة.
- **Required Facts**: ["النص يذكر أن الموارد الدولية أو المالية وحدها غير كافية.", "النص يؤكد على ضرورة التركيز على التنمية التقنية.", "الهدف هو تنمية التقنية لتحقيق الفعالية."]
- **Reference Page Numbers**: [10]
- **Reference Chunk IDs**: `['432d866e-d0c8-4065-9132-e3310c466f4a']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "ييت بفعاليتهيييا التعليميييية والتنظيميييية واإلنتاجيية وننشيب بالتيالي مؤسسيات ومنظميات تتعاميل ميط يذ التقنيية بضيي . تنتجها وتعلمها وتتدصها 4. ال يكفيي أن ت صيص أي دولية صربيية ..."

---

### Case TC-005

- **Document Filename**: Arabic Document 2.pdf
- **Document ID**: `1ef24635-4f7f-4849-93a7-3a4fc6bf1560`
- **Category**: `explanation`
- **Source Language**: `ar`
- **Question Language**: `ar`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > كيف يصف النص أثر دمج التقنيات الحديثة مثل الذكاء الاصطناعي وأنظمة قواعد البيانات على البيئة التعليمية؟
- **Reference Answer**:
  > يُشير النص إلى أن دمج التقنيات الحديثة مثل الذكاء الاصطناعي وأنظمة قواعد البيانات يخلق بيئة تعليمية تفصيلية وحيوية، ويساهم في تسهيل نقل المعرفة التقنية الحديثة، مما ينعكس إيجاباً على مجانية التعليم وتوسيع فرص التعلم.
- **Required Facts**: ["النص يذكر أن دمج التقنيات الحديثة يخلق بيئة تفصيلية وحيوية.", "النص يوضح أن ذلك ينعكس إيجاباً على مجانية التعليم.", "النص يذكر أمثلة مثل الذكاء الاصطناعي وأنظمة قواعد البيانات."]
- **Reference Page Numbers**: [1]
- **Reference Chunk IDs**: `['03c9f2a0-4cd4-451b-9c3d-e209be1310e2']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "اكمر الذي حيدا بيالتربويين إلي تتنيي أنمياو وبيدائل تعليميية مت يو ، وتيوفير بيئة تفاصلية وحيويية صلي د جية صاليية مين المرونية والكفيا ؛ لشيد انتتيا الميتعل وتجذبه إليها . في وي ر..."

---

### Case TC-006

- **Document Filename**: Arabic Document 2.pdf
- **Document ID**: `1ef24635-4f7f-4849-93a7-3a4fc6bf1560`
- **Category**: `multi_chunk`
- **Source Language**: `ar`
- **Question Language**: `ar`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > ما هو الدور الذي تلعبه تقنيتي الواقع الافتراضي والويب الافتراضي في تحسين استراتيجيات التعلم داخل البيئة الجامعية وفقًا للنص؟
- **Reference Answer**:
  > يُشير النص إلى أن تقنيتي الواقع الافتراضي (Virtual Reality) والويب الافتراضي (World Wide Web) تُعدّان من المكوّنات الأساسية التي أدت إلى ظهور تقنيات عديدة في مجال التعليم. فهما يوفّران وسيلةً افتراضيةً تُسهل على المعلم تقديم استراتيجيات تعليمية وعلمية، وتُعزّزان التعلم داخل الجامعات حيث يصبح التواجد الفعلي غير أساسي، مما يتيح للطلاب الاستفادة من بيئة تعليمية متكاملة ومُتاحة عبر الإنترنت.
- **Required Facts**: ["ذكر النص تقنيتي الواقع الافتراضي (Virtual Reality) والويب الافتراضي (World Wide Web) كأمثلة على التقنيات الحديثة في التعليم.", "ذكر النص أن الويب الافتراضي يسهّل استراتيجيات تعليمية وعلمية في البيئة الجامعية.", "أشار النص إلى أن التواجد داخل الجامعة يصبح غير أساسي بفضل هذه التقنيات."]
- **Reference Page Numbers**: [5]
- **Reference Chunk IDs**: `['f763efd9-35c8-4663-80bc-2cc7b858c8da', '3db2e0df-989e-4066-b5db-0d6431660419']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "- التقنيات الحدي: ثة وأثرها على التعليم والتعلم  إن التقييدم السييريط فييي مجييال االتصيياالت والصييناصات الترفيهييية وظييرو التنيافس فيي سيوق التجيا العالميية فيي مجيال الضاسيع صو..."
  * Chunk 2: "يتعل تشيكل وفيى نميل المضتيوى التعليميي اليذي ،يقدمه المعل ل لتته وفي مقدمتها الواغط االفترا ي الذي ييسر تتام ا استراتيجيات تعليميية ت علميّية أوسيط شيموالً وأكثير تي ًبيراً ، كميا..."

---

### Case TC-007

- **Document Filename**: Arabic Document 2.pdf
- **Document ID**: `1ef24635-4f7f-4849-93a7-3a4fc6bf1560`
- **Category**: `multi_chunk`
- **Source Language**: `ar`
- **Question Language**: `ar`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > كيف يربط النص بين المعايير الرئيسة للدخول إلى مجال الفضاء وتكنولوجيا المعلومات والهيكلة التنيوية للنظام المؤسسي، وما هو الهدف النهائي من هذا الربط في سياق تنمية التقنية التعليمية؟
- **Reference Answer**:
  > النص يحدد أن الدخول إلى مجال الفضاء وتكنولوجيا المعلومات يتطلب معايير رئيسية تشمل الفضاء، تكنولوجيا المعلومات، الاتصالات، المعرفة، الجوانب الفكرية، التقنية، الثقافية والعلمية. بعد ذلك يشير إلى ضرورة إنشاء هيكلة تنيوية للنظام المؤسسي تُدمج تقنيات المعلومات والاتصالات الحديثة مع العملية التعليمية، بحيث تصبح جزءاً من الممارسة التعليمية وتدعم التعلم المستمر، التعلم الذاتي، والتعلم المتعدد الوسائط. الهدف النهائي من هذا الربط هو تنمية التقنية وتطوير الذكاء الاصطناعي في البيئة التعليمية.
- **Required Facts**: ["المعايير الرئيسة للدخول تشمل الفضاء، تكنولوجيا المعلومات، الاتصالات، المعرفة، الجوانب الفكرية، التقنية، الثقافية والعلمية", "ضرورة إنشاء هيكلة تنيوية للنظام المؤسسي ودمج تقنيات المعلومات والاتصالات الحديثة مع العملية التعليمية", "الهدف هو تنمية التقنية وتطوير الذكاء الاصطناعي في البيئة التعليمية"]
- **Reference Page Numbers**: [10, 11]
- **Reference Chunk IDs**: `['432d866e-d0c8-4065-9132-e3310c466f4a', 'e254bd73-4a6d-4853-9890-57db6575341a']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "ييت بفعاليتهيييا التعليميييية والتنظيميييية واإلنتاجيية وننشيب بالتيالي مؤسسيات ومنظميات تتعاميل ميط يذ التقنيية بضيي . تنتجها وتعلمها وتتدصها 4. ال يكفيي أن ت صيص أي دولية صربيية ..."
  * Chunk 2: "5. المعتييير الرئيسيييي لليييدخول إلييي صيييال الفضيييائيات وتكنولوجييييا المعلوميييات واالتصاالت وإبيدام المعرفية ييت صين ال رييى معرفية إيقاصيات العصير الفكريية والتقنييية وصالمي..."

---

### Case TC-008

- **Document Filename**: Arabic Document 2.pdf
- **Document ID**: `1ef24635-4f7f-4849-93a7-3a4fc6bf1560`
- **Category**: `comparison`
- **Source Language**: `ar`
- **Question Language**: `ar`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > ما الفرق بين نقاط القوة ونقاط الضعف التي تم الكشف عنها في استخدام تكنولوجيا المعلومات والاتصالات في الخدمات التعليمية وفقًا للنص؟
- **Reference Answer**:
  > النص يذكر أن هناك عملية كشف لكل من نقاط القوة ونقاط الضعف في توظيف تكنولوجيا المعلومات والاتصالات داخل الخدمات التعليمية. نقاط القوة تمثل الجوانب التي تدعم وتحسن جودة الخدمات التعليمية وتساعد على الاستفادة من التقنية، بينما نقاط الضعف تشير إلى الجوانب التي تعيق أو تقلل من فعالية هذه التقنية وتؤدي إلى صعوبات ومعوّقات تحول دون الاستفادة الكاملة منها.
- **Required Facts**: ["وجود عملية كشف لنقاط القوة في تكنولوجيا المعلومات والاتصالات في الخدمات التعليمية", "وجود عملية كشف لنقاط الضعف في تكنولوجيا المعلومات والاتصالات في الخدمات التعليمية", "الإشارة إلى الصعوبات والمعوّقات التي تعيق الاستفادة من هذه التقنية"]
- **Reference Page Numbers**: [2]
- **Reference Chunk IDs**: `['89d9a844-6fcd-4442-a950-057e775c1873']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "يييا المعلوميات واالتصياالت فيي ال يدمات التعليميية ، وأخييراً الكشيف صين نقياو القيو والضعف في معال التنيية التضتيية لتكنولوجييا المعلوميات واالتصياالت فيي التليدان الناميية لتضدي..."

---

### Case TC-009

- **Document Filename**: Arabic Document 2.pdf
- **Document ID**: `1ef24635-4f7f-4849-93a7-3a4fc6bf1560`
- **Category**: `summary`
- **Source Language**: `ar`
- **Question Language**: `ar`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > ما الهدف من توفير بيئة تعليمية تفصيلية وحيوية كما يذكر النص؟
- **Reference Answer**:
  > يهدف النص إلى جذب المتعلمين وتعزيز تفاعلهم من خلال توفير بيئة تعليمية تفصيلية وحيوية، مما يسهم في تحسين جودة التعلم.
- **Required Facts**: ["النص يذكر توفير بيئة تفصيلية وحيوية", "الهدف هو جذب المتعلمين وتعزيز تفاعلهم"]
- **Reference Page Numbers**: [1]
- **Reference Chunk IDs**: `['03c9f2a0-4cd4-451b-9c3d-e209be1310e2']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "اكمر الذي حيدا بيالتربويين إلي تتنيي أنمياو وبيدائل تعليميية مت يو ، وتيوفير بيئة تفاصلية وحيويية صلي د جية صاليية مين المرونية والكفيا ؛ لشيد انتتيا الميتعل وتجذبه إليها . في وي ر..."

---

### Case TC-010

- **Document Filename**: Arabic Document 2.pdf
- **Document ID**: `1ef24635-4f7f-4849-93a7-3a4fc6bf1560`
- **Category**: `unanswerable`
- **Source Language**: `ar`
- **Question Language**: `ar`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `False`
- **Expected Behavior**: `fallback`
- **Review Status**: `pending`
- **Natural Student Question**:
  > ما هو عدد الموظفين الذين يعملون في المؤسسة المذكورة في النص؟
- **Unanswerable Rationale**: The snippet provided contains only vague references to educational, organizational, and production activities, technical institutions, and general challenges. It does not include any quantitative data such as the number of staff members employed by the institution, nor does the broader document (as far as the excerpt shows) mention staffing figures. Therefore, the answer cannot be derived from the given context.

---

### Case TC-011

- **Document Filename**: English Document 1.pdf
- **Document ID**: `0d453a69-e504-48c6-bc6c-09e801756218`
- **Category**: `direct_factual`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > What are the three phases in which generative AI operates?
- **Reference Answer**:
  > Generative AI operates in three phases: Training, Tuning, and Generation (which includes evaluation and retuning).
- **Required Facts**: ["Generative AI operates in three phases", "The phases are Training, Tuning, and Generation (evaluation and retuning)"]
- **Reference Page Numbers**: [4]
- **Reference Chunk IDs**: `['15a40911-a9ee-4f4f-aeb7-2e82cd609433']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "4 Generative AI  How generative AI works Generative AI operates in three phases: • Training, to create a foundation model that can serve as the basis of multiple gen AI application..."

---

### Case TC-012

- **Document Filename**: English Document 1.pdf
- **Document ID**: `0d453a69-e504-48c6-bc6c-09e801756218`
- **Category**: `direct_factual`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > What kinds of new content can generative AI create, and how is its training objective different from that of a typical predictive machine‑learning model?
- **Reference Answer**:
  > Generative AI can create new content such as text, images, audio, video, or code. Unlike typical predictive models that are trained to make predictions about a specific dataset, a generative AI model is trained to create new data that resembles the data it was trained on.
- **Required Facts**: ["Generative AI can create new content—text, images, audio, video, or code.", "It is trained to create new data rather than make predictions about a specific dataset."]
- **Reference Page Numbers**: [1]
- **Reference Chunk IDs**: `['3bc87535-178c-4bc0-994c-3a6119adc775']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "Selected Labs in AI Generative AI Spring 2026  AI World 2  Generative AI • Generative AI (short for generative artificial intelligence) refers to a type of AI that can create new c..."

---

### Case TC-013

- **Document Filename**: English Document 1.pdf
- **Document ID**: `0d453a69-e504-48c6-bc6c-09e801756218`
- **Category**: `direct_factual`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > If a user inputs a sentence that contains both the words "hello" and "bye", which response will the chatbot return and why?
- **Reference Answer**:
  > The chatbot will return a random response from the "hello" list (e.g., "Hi there!", "Hello!", or "Hey! How can I help you?"). This is because the function iterates over the keys of the `responses` dictionary in the order they are defined ("hello", "how are you", "bye", "default") and returns the first matching response it finds, exiting the loop immediately.
- **Required Facts**: ["The `for key in responses:` loop checks keys in the order they appear in the dictionary ("hello" before "bye").", "When a key is found in the user input, the function returns `random.choice(responses[key])` and stops further checking.", "The dictionary defines the "hello" key before the "bye" key."]
- **Reference Page Numbers**: [17]
- **Reference Chunk IDs**: `['eef4057d-6e37-43ce-8a91-5d48bb04accd']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "simple python code for chatbot • import random • # Predefined responses • responses = { • "hello": ["Hi there!", "Hello!", "Hey! How can I help you?"], • "how are you": ["I'm just ..."

---

### Case TC-014

- **Document Filename**: English Document 1.pdf
- **Document ID**: `0d453a69-e504-48c6-bc6c-09e801756218`
- **Category**: `explanation`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > How does the attention map generated by a transformer contribute to its ability to understand context when producing new text?
- **Reference Answer**:
  > A transformer first encodes each word in a text corpus as a token. It then creates an attention map that captures the relationships between every token and all other tokens. This attention map provides the transformer with information about how words relate to each other, allowing it to grasp the context of the sentence and generate new text that reflects the intended meaning.
- **Required Facts**: ["A transformer encodes each word as a token.", "It generates an attention map that captures each token’s relationships with all other tokens.", "The attention map helps the transformer understand context when generating new text."]
- **Reference Page Numbers**: [8]
- **Reference Chunk IDs**: `['44b482c6-6617-4e22-8a8c-e2130352c8fc']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "Large Language Models (LLMs) • In 2017, researchers at Google introduced the transformer architecture, which has been used to develop large language models, like those that power C..."

---

### Case TC-015

- **Document Filename**: English Document 1.pdf
- **Document ID**: `0d453a69-e504-48c6-bc6c-09e801756218`
- **Category**: `explanation`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > How does the training phase of a foundation model use large-scale raw data and fill‑in‑the‑blank tasks to continuously reduce the gap between its predictions and the actual data?
- **Reference Answer**:
  > In the training phase, practitioners feed a deep learning algorithm with massive amounts of raw, unstructured, unlabeled data—often terabytes sourced from the internet or similar large repositories. The algorithm then carries out millions of fill‑in‑the‑blank exercises, where it tries to predict the next element in a sequence, such as the next word in a sentence, the next pixel or object in an image, or the next command in a line of code. After each prediction, the model compares its output to the true next element and adjusts its internal parameters to minimize the difference between the predicted and actual values, repeating this process iteratively to continually shrink the prediction error.
- **Required Facts**: ["Training uses huge volumes of raw, unstructured, unlabeled data (e.g., terabytes from the internet).", "The algorithm performs fill‑in‑the‑blank exercises predicting the next element in a sequence (word, image element, code command).", "It continually adjusts itself to minimize the difference between its predictions and the actual data."]
- **Reference Page Numbers**: [7]
- **Reference Chunk IDs**: `['a59ae8a1-20d6-4527-b916-5c247b417107']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "Training Phase • To create a foundation model, practitioners train a deep learning algorithm on huge volumes of raw, unstructured, unlabeled data e.g., terabytes of data from the i..."

---

### Case TC-016

- **Document Filename**: English Document 1.pdf
- **Document ID**: `0d453a69-e504-48c6-bc6c-09e801756218`
- **Category**: `multi_chunk`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > What are the key aspects of the training phase for foundation models, and how do these aspects correspond to the scale, training method, and capabilities described for large language models?
- **Reference Answer**:
  > The training phase for foundation models involves training a deep‑learning algorithm on massive amounts of raw, unstructured, unlabeled data—often terabytes from the internet. During this phase the model performs millions of fill‑in‑the‑blank tasks, trying to predict the next element in a sequence (such as the next word, image part, or code command) and continuously adjusts to reduce the gap between its predictions and the actual data. Large language models share similar characteristics: they are trained on very large text datasets (books, articles, websites) containing billions of words, using deep learning techniques based on the Transformer architecture. This large‑scale training gives LLMs capabilities such as answering questions, translating text, summarizing content, and generating stories. Thus, the foundation‑model training process of using huge raw data and predictive fill‑in‑the‑blank tasks underlies the scale and deep‑learning‑Transformer method that enable the diverse capabilities of LLMs.
- **Required Facts**: ["Foundation model training uses huge volumes of raw, unstructured, unlabeled data and fill‑in‑the‑blank exercises to predict the next element and minimize prediction error.", "Large language models are trained on massive text datasets with billions of words, using deep learning based on the Transformer architecture.", "LLMs can answer questions, translate, summarize, and generate stories as a result of this large‑scale training."]
- **Reference Page Numbers**: [7, 9]
- **Reference Chunk IDs**: `['a59ae8a1-20d6-4527-b916-5c247b417107', '810156c8-9520-40cf-9836-53794c5a9612']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "Training Phase • To create a foundation model, practitioners train a deep learning algorithm on huge volumes of raw, unstructured, unlabeled data e.g., terabytes of data from the i..."
  * Chunk 2: "Large Language Models (LLMs) • A Large Language Model is an AI trained on massive amounts of text data to understand and generate human language. 9  Large Language Models - Feature..."

---

### Case TC-017

- **Document Filename**: English Document 1.pdf
- **Document ID**: `0d453a69-e504-48c6-bc6c-09e801756218`
- **Category**: `multi_chunk`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > In generative AI, how do large language models differ from other foundation models, and what transformer-based mechanism introduced in 2017 enables them to capture contextual relationships between tokens?
- **Reference Answer**:
  > Large language models (LLMs) are the most common foundation models used today and are specifically created for text‑generation applications, whereas other foundation models are designed for generating images, video, sound, music, or multimodal content. The ability of LLMs to understand context comes from the transformer architecture that Google introduced in 2017. A transformer encodes each word in a corpus as a token and then builds an attention map that records the relationships between every token and all other tokens; this attention map allows the model to grasp contextual meaning when it generates new text.
- **Required Facts**: ["LLMs are the most common foundation models for text generation, while other foundation models support image, video, sound, music, and multimodal content.", "The transformer architecture was introduced by Google in 2017 and is used to develop large language models.", "Transformers encode words as tokens and generate an attention map that captures relationships between all tokens, helping the model understand context."]
- **Reference Page Numbers**: [6, 8]
- **Reference Chunk IDs**: `['80137b41-3073-4afc-8157-e46e832cfef6', '44b482c6-6617-4e22-8a8c-e2130352c8fc']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "Training Phase • Generative AI begins with a foundation model, a deep learning model that serves as the basis for multiple different types of generative AI applications. • The most..."
  * Chunk 2: "Large Language Models (LLMs) • In 2017, researchers at Google introduced the transformer architecture, which has been used to develop large language models, like those that power C..."

---

### Case TC-018

- **Document Filename**: English Document 1.pdf
- **Document ID**: `0d453a69-e504-48c6-bc6c-09e801756218`
- **Category**: `comparison`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > How does the content stored in the variable "summary" differ from the content stored in the variable "text" in the provided code snippet?
- **Reference Answer**:
  > In the snippet, "text" holds the original input text, while "summary" contains the condensed version produced by the summarizer function, which limits the output to a maximum of 60 tokens.
- **Required Facts**: ["The variable "text" is the original input.", "The summarizer function creates a shortened version with max_length=60.", "The result of the summarizer is stored in the variable "summary"."]
- **Reference Page Numbers**: [16]
- **Reference Chunk IDs**: `['5fe1163e-6944-46ac-9447-84d33da8c7f6']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: ". • """ • # Generate a summary • summary = summarizer(text, max_length=60) • # Print the summary • print("Summary:") • print(summary) 16 هنا اديله نص يلخصهولي..."

---

### Case TC-019

- **Document Filename**: English Document 1.pdf
- **Document ID**: `0d453a69-e504-48c6-bc6c-09e801756218`
- **Category**: `summary`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > What response does the chatbot give when the user's input does not contain any of the predefined keywords?
- **Reference Answer**:
  > The function first converts the input to lowercase, then iterates over all keys in the responses dictionary. If none of the keys are found in the input, it returns a random choice from the "default" list, which contains the message "I'm sorry, I don't understand that. Can you rephrase?".
- **Required Facts**: ["The function lowercases the user input.", "It loops through each key in the responses dictionary.", "If no key matches, it returns a random choice from responses["default"]."]
- **Reference Page Numbers**: [17]
- **Reference Chunk IDs**: `['eef4057d-6e37-43ce-8a91-5d48bb04accd']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "simple python code for chatbot • import random • # Predefined responses • responses = { • "hello": ["Hi there!", "Hello!", "Hey! How can I help you?"], • "how are you": ["I'm just ..."

---

### Case TC-020

- **Document Filename**: English Document 1.pdf
- **Document ID**: `0d453a69-e504-48c6-bc6c-09e801756218`
- **Category**: `unanswerable`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `False`
- **Expected Behavior**: `fallback`
- **Review Status**: `pending`
- **Natural Student Question**:
  > What is the name of the pre‑trained model that the summarizer function utilizes in the code example?
- **Unanswerable Rationale**: The provided snippet only shows how the summarizer is called with a text input and a max_length parameter, and it prints the resulting summary. It does not specify which pre‑trained model (e.g., BART, T5, Pegasus) the summarizer is based on, nor does the broader document contain that information. Therefore, the answer cannot be derived from the given context.

---

### Case TC-021

- **Document Filename**: Document 3 Advanced.pdf
- **Document ID**: `6be74837-9a43-44ff-bba2-eebaeeb10823`
- **Category**: `direct_factual`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > What operational principle does a Global Navigation Satellite System (GNSS) use to determine a location?
- **Reference Answer**:
  > GNSS determines a location by using trilateration with signals from at least four satellites.
- **Required Facts**: ["GNSS uses trilateration using signals from at least four satellites to determine location."]
- **Reference Page Numbers**: [4]
- **Reference Chunk IDs**: `['061b3eb1-18aa-49d6-8b66-67f5b86aa521']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "Global Navigation Satellite Systems (GNSS) • A system of multiple satellite constellations providing worldwide positioning. • Key Global Systems: GPS (USA), GLONASS (Russia), Galil..."

---

### Case TC-022

- **Document Filename**: Document 3 Advanced.pdf
- **Document ID**: `6be74837-9a43-44ff-bba2-eebaeeb10823`
- **Category**: `direct_factual`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > What types of satellite navigation systems are described and how does their coverage differ?
- **Reference Answer**:
  > The snippet describes two types: Global Navigation Satellite Systems (GNSS), which provide worldwide coverage, and Regional Navigation Satellite Systems (RNSS), which provide coverage for specific regions.
- **Required Facts**: ["Global Navigation Satellite Systems (GNSS) provide worldwide coverage", "Regional Navigation Satellite Systems (RNSS) provide coverage for specific regions", "These are the two types mentioned in the text"]
- **Reference Page Numbers**: [1]
- **Reference Chunk IDs**: `['1d7287da-ae74-4359-b8cc-c3c538af7199']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "Wireless and Mobile Networks Spring Semester 2025-2026 IT439 9  Part 2 Satellites  Satellite Navigation Systems Satellite Navigation Systems are networks of satellites that provide..."

---

### Case TC-023

- **Document Filename**: Document 3 Advanced.pdf
- **Document ID**: `6be74837-9a43-44ff-bba2-eebaeeb10823`
- **Category**: `direct_factual`
- **Source Language**: `en`
- **Question Language**: `ar`
- **Cross-lingual Status**: `True`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > ما هو اسم الجهة المشغلة لنظام Galileo ومتى بدأ تشغيله الكامل وفقًا للجدول المقارن؟
- **Reference Answer**:
  > الجهة المشغلة لنظام Galileo هي وكالة الاتحاد الأوروبي لبرنامج الفضاء (EUSPA)، وبدأ تشغيله الكامل في عام 2016.
- **Required Facts**: ["المشغل الرسمي لنظام Galileo هو European Union Agency for the Space Programme (EUSPA)", "سنة بدء التشغيل الكامل لنظام Galileo هي 2016"]
- **Reference Page Numbers**: [12]
- **Reference Chunk IDs**: `['911c30eb-ff0b-45d6-992e-b7bb87b107ff']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "How GPS works? (cont.) Differential GPS (DGPS) Accuracy Improvement: • Reduces errors from ~3-5 meters to sub-meter or even centimeter-level accuracy  GNSSs Comparison Feature GPS ..."

---

### Case TC-024

- **Document Filename**: Document 3 Advanced.pdf
- **Document ID**: `6be74837-9a43-44ff-bba2-eebaeeb10823`
- **Category**: `explanation`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > How does Differential GPS (DGPS) improve the accuracy of standard GPS signals?
- **Reference Answer**:
  > Differential GPS improves accuracy by using a ground‑based reference station located at a known position. The station receives the GPS signals and calculates the errors caused by atmospheric conditions and satellite clock inaccuracies. It then creates correction data, which is sent to nearby GPS receivers via radio or the internet. The receivers apply these corrections to their own measurements, resulting in a more precise position.
- **Required Facts**: ["A ground‑based reference station at a known location receives GPS signals and calculates errors.", "The station generates correction data and transmits it to nearby GPS receivers.", "GPS receivers apply the corrections to refine their positioning accuracy."]
- **Reference Page Numbers**: [7]
- **Reference Chunk IDs**: `['73482c7e-b5bc-495f-92c2-ef306da8d5dd']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "How GPS works? (cont.) Trilateration  How GPS works? (cont.) Trilateration  How GPS works? (cont.) Trilateration  How GPS works? (cont.) Trilateration  How GPS works? (cont.) Diffe..."

---

### Case TC-025

- **Document Filename**: Document 3 Advanced.pdf
- **Document ID**: `6be74837-9a43-44ff-bba2-eebaeeb10823`
- **Category**: `explanation`
- **Source Language**: `en`
- **Question Language**: `ar`
- **Cross-lingual Status**: `True`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > ما هو الفرق بين الأخطاء التي تصححها محطة الإشارة الأرضية في نظام GPS التفاضلي (DGPS) مقارنةً بالأخطاء التي تؤثر على إشارات GPS التقليدية، وكيف يتم حساب هذه الأخطاء؟
- **Reference Answer**:
  > في نظام GPS التفاضلي (DGPS) تُستخدم محطة إشارة أرضية تقع في موقع معروف لتلقي إشارات الأقمار الصناعية. تقوم هذه المحطة بحساب الأخطاء الموجودة في إشارات GPS التقليدية، وتحديدًا الأخطاء الناجمة عن الظروف الجوية وعدم دقة ساعات الأقمار الصناعية. بعد حساب هذه الأخطاء، تُرسل بيانات التصحيح إلى مستقبلات GPS القريبة عبر إشارات راديوية أو الإنترنت، حيث تُطبق المستقبلات هذه التصحيحات لتقليل الأخطاء وتحسين دقة تحديد الموقع.
- **Required Facts**: ["محطة الإشارة الأرضية في موقع معروف تستقبل إشارات GPS.", "المحطة تحسب الأخطاء الناجمة عن الظروف الجوية وعدم دقة ساعات الأقمار الصناعية.", "بيانات التصحيح تُنقل إلى مستقبلات GPS القريبة لتطبيقها وتحسين دقة الموقع."]
- **Reference Page Numbers**: [7]
- **Reference Chunk IDs**: `['73482c7e-b5bc-495f-92c2-ef306da8d5dd']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "How GPS works? (cont.) Trilateration  How GPS works? (cont.) Trilateration  How GPS works? (cont.) Trilateration  How GPS works? (cont.) Trilateration  How GPS works? (cont.) Diffe..."

---

### Case TC-026

- **Document Filename**: Document 3 Advanced.pdf
- **Document ID**: `6be74837-9a43-44ff-bba2-eebaeeb10823`
- **Category**: `multi_chunk`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > How do the civilian positioning accuracies compare among GPS, GLONASS, Galileo, and BeiDou, and how many operational satellites does each system have?
- **Reference Answer**:
  > GPS (USA) has about 31 operational satellites (out of a nominal 24) and provides civilian positioning accuracy of roughly 5 meters, which can be improved with WAAS/EGNOS. GLONASS (Russia) operates 24 satellites and offers civilian accuracy of about 5–10 meters. Galileo (EU) has 28 operational satellites and can achieve civilian accuracy of less than 1 meter when using its High Accuracy Service. BeiDou (China) has more than 30 operational satellites and delivers civilian accuracy of about 2.5–5 meters globally, with sub‑meter accuracy in regional BDS‑3 coverage.
- **Required Facts**: ["GPS: 31 operational satellites, civilian accuracy ~5 m (better with WAAS/EGNOS).", "GLONASS: 24 operational satellites, civilian accuracy ~5–10 m.", "Galileo: 28 operational satellites, civilian accuracy <1 m with High Accuracy Service.", "BeiDou: >30 operational satellites, civilian accuracy ~2.5–5 m globally (<1 m regionally)."]
- **Reference Page Numbers**: [14, 16]
- **Reference Chunk IDs**: `['fd7da736-0a4d-4082-a9f0-886168a9e660', '79a25218-5cce-43bd-8090-8e53cd5881c3']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "GNSSs Comparison Feature GPS (USA) GLONASS (Russia) Galileo (EU) BeiDou (China) Orbit Type MEO (20,200 km) MEO (19,100 km) MEO (23,222 km) MEO + IGSO + GEO No. of Satellites (Nomin..."
  * Chunk 2: "GNSSs Comparison Feature GPS GLONASS Galileo BeiDou Civilian Accuracy ~5 m (better with WAAS/EGNOS) ~5–10 m <1 m (with High Accuracy Service) ~2.5–5 m (global), <1 m (regional BDS-..."

---

### Case TC-027

- **Document Filename**: Document 3 Advanced.pdf
- **Document ID**: `6be74837-9a43-44ff-bba2-eebaeeb10823`
- **Category**: `multi_chunk`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > Which global navigation satellite system provides the best civilian positioning accuracy, and how does its orbital configuration and number of operational satellites compare to the system with the largest nominal satellite count?
- **Reference Answer**:
  > The Galileo system (EU) provides the best civilian positioning accuracy, achieving less than 1 meter when the High Accuracy Service is used. Galileo uses a medium Earth orbit (MEO) at an altitude of 23,222 km, has three orbital planes with an inclination of 56°, and operates a nominal constellation of 24 satellites, of which 28 are operational as of 2024. In contrast, the system with the largest nominal satellite count is BeiDou (China), which has a mixed constellation of MEO, inclined geosynchronous orbit (IGSO), and geostationary orbit (GEO) satellites (MEO + IGSO (5) + GEO (3)). BeiDou’s nominal constellation consists of 35 satellites, with more than 30 operational satellites.
- **Required Facts**: ["Galileo civilian accuracy is <1 m with High Accuracy Service.", "Galileo orbital type is MEO (23,222 km), 3 orbital planes, inclination 56°, 28 operational satellites.", "BeiDou has the largest nominal satellite count (35) with a mixed MEO+IGSO+GEO constellation and over 30 operational satellites."]
- **Reference Page Numbers**: [14, 16]
- **Reference Chunk IDs**: `['fd7da736-0a4d-4082-a9f0-886168a9e660', '79a25218-5cce-43bd-8090-8e53cd5881c3']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "GNSSs Comparison Feature GPS (USA) GLONASS (Russia) Galileo (EU) BeiDou (China) Orbit Type MEO (20,200 km) MEO (19,100 km) MEO (23,222 km) MEO + IGSO + GEO No. of Satellites (Nomin..."
  * Chunk 2: "GNSSs Comparison Feature GPS GLONASS Galileo BeiDou Civilian Accuracy ~5 m (better with WAAS/EGNOS) ~5–10 m <1 m (with High Accuracy Service) ~2.5–5 m (global), <1 m (regional BDS-..."

---

### Case TC-028

- **Document Filename**: Document 3 Advanced.pdf
- **Document ID**: `6be74837-9a43-44ff-bba2-eebaeeb10823`
- **Category**: `comparison`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > What are the differences in the frequency bands used by GPS and GLONASS?
- **Reference Answer**:
  > GPS operates on three main frequency bands: L1 at 1575.42 MHz, L2 at 1227.60 MHz, and L5 at 1176.45 MHz. GLONASS, on the other hand, uses L1 at 1602 MHz, L2 at 1246 MHz, and L3 at 1202 MHz. Thus, each system employs distinct carrier frequencies for its L‑band signals.
- **Required Facts**: ["GPS frequency bands: L1 1575.42 MHz, L2 1227.60 MHz, L5 1176.45 MHz", "GLONASS frequency bands: L1 1602 MHz, L2 1246 MHz, L3 1202 MHz"]
- **Reference Page Numbers**: [15]
- **Reference Chunk IDs**: `['455886e0-bd41-44ae-8de2-497d39e01be0']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "GNSSs Comparison GPS GLONASS Galileo BeiDou Frequency Bands L1 (1575.42 MHz), L2 (1227.60 MHz), L5 (1176.45 MHz) L1 (1602 MHz), L2 (1246 MHz), L3 (1202 MHz) E1 (1575.42 MHz), E5a (..."

---

### Case TC-029

- **Document Filename**: Document 3 Advanced.pdf
- **Document ID**: `6be74837-9a43-44ff-bba2-eebaeeb10823`
- **Category**: `summary`
- **Source Language**: `en`
- **Question Language**: `en`
- **Cross-lingual Status**: `False`
- **Answerable Status**: `True`
- **Expected Behavior**: `answer`
- **Review Status**: `pending`
- **Natural Student Question**:
  > What are the launch years for GPS, GLONASS, Galileo, and BeiDou, and which of these systems reached full operational status most recently?
- **Reference Answer**:
  > According to the table, GPS was first launched in 1978, GLONASS in 1982, Galileo in 2011 (with full operational capability achieved in 2016), and BeiDou in 2000 (with the BDS‑3 version becoming operational in 2020). The most recent full operational status among them is BeiDou, which reached it in 2020.
- **Required Facts**: ["GPS first launch year: 1978", "GLONASS first launch year: 1982", "Galileo first launch year: 2011 and full ops in 2016", "BeiDou first launch year: 2000 and BDS‑3 full ops in 2020"]
- **Reference Page Numbers**: [12]
- **Reference Chunk IDs**: `['911c30eb-ff0b-45d6-992e-b7bb87b107ff']`
- **Reference Contexts/Excerpts**:
  * Chunk 1: "How GPS works? (cont.) Differential GPS (DGPS) Accuracy Improvement: • Reduces errors from ~3-5 meters to sub-meter or even centimeter-level accuracy  GNSSs Comparison Feature GPS ..."

---

### Case TC-030

- **Document Filename**: Document 3 Advanced.pdf
- **Document ID**: `6be74837-9a43-44ff-bba2-eebaeeb10823`
- **Category**: `unanswerable`
- **Source Language**: `en`
- **Question Language**: `ar`
- **Cross-lingual Status**: `True`
- **Answerable Status**: `False`
- **Expected Behavior**: `fallback`
- **Review Status**: `pending`
- **Natural Student Question**:
  > ما هو متوسط عدد الأقمار الصناعية التي تكون في مدار نظام GPS في أي لحظة؟
- **Unanswerable Rationale**: The snippet provides details on DGPS accuracy improvement, launch years, operators, and global coverage for GPS and other GNSS, but it does not include any information about the current number of satellites in the GPS constellation. Therefore, the answer cannot be found in the provided context.