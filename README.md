# RHBK 26.4 sur OpenShift — GitOps, thème québécois et action requise

Déploiement de **Red Hat Build of Keycloak (RHBK) 26.4** sur OpenShift selon les
principes **GitOps**, avec une image personnalisée construite par un pipeline
**Tekton**. La personnalisation comprend :

- un **thème de connexion** sombre « quebec » ;
- une **action requise** personnalisée `accepter-conditions-utilisation`
  (acceptation des conditions d'utilisation) ;
- un **royaume de démonstration `quebec`** qui met en œuvre le thème et l'action
  requise.

L'image est construite à partir des modules Maven `theme/` et `required-action/`
puis optimisée (`kc.sh build`) dans un `Containerfile` multi-étapes. Le pipeline
pousse l'image dans le registre interne d'OpenShift et met à jour la ressource
`Keycloak`. La synchronisation continue est assurée par **Argo CD** (OpenShift
GitOps).

---

## 1. Architecture

```
GitHub (ce dépôt)
   │
   ├── Argo CD (OpenShift GitOps)  ──►  applique gitops/overlays/production
   │                                      ├── namespace keycloak
   │                                      ├── PostgreSQL (StatefulSet + Service)
   │                                      ├── Secret BD + Certificate (cert-manager)
   │                                      ├── Keycloak CR (opérateur RHBK)
   │                                      ├── KeycloakRealmImport « quebec »
   │                                      └── Pipeline Tekton + déclencheurs (webhook)
   │
   └── Webhook GitHub  ──►  EventListener  ──►  PipelineRun
                                                 clone → maven → buildah → openshift-client
                                                 (construit l'image, pousse, met à jour le CR)
```

Le pipeline n'utilise **que des tâches fournies par Red Hat** (`git-clone`,
`maven`, `buildah`, `openshift-client`), référencées via le **résolveur
« cluster »** dans l'espace de noms `openshift-pipelines` (les `ClusterTask`
ayant été retirées d'OpenShift Pipelines).

---

## 2. Prérequis

### 2.1 Opérateurs OpenShift (installés au préalable)

| Opérateur | Rôle | Espace de noms |
|-----------|------|----------------|
| **Red Hat Build of Keycloak** | Gère les ressources `Keycloak` et `KeycloakRealmImport` | `keycloak` (ou global) |
| **OpenShift GitOps** (Argo CD) | Synchronise le dépôt Git vers le cluster | `openshift-gitops` |
| **OpenShift Pipelines** (Tekton) | Fournit les tâches Red Hat et exécute le pipeline | `openshift-pipelines` |
| **cert-manager** | Émet le certificat TLS de Keycloak | `cert-manager` |
| **Grafana Operator** (communautaire, `grafana-operator` v5) | Gère les ressources `Grafana`, `GrafanaDatasource`, `GrafanaDashboard` | `keycloak` (ou global) |

> On suppose que **tous ces opérateurs sont déjà installés** et que leurs
> instances par défaut fonctionnent (instance Argo CD `openshift-gitops`,
> opérateur Pipelines avec les tâches dans `openshift-pipelines`).
>
> Le **Grafana Operator** n'est requis que pour l'observabilité (§9). Il fournit
> les CRD `grafana.integreatly.org/v1beta1`. Installation via OperatorHub ou :
>
> ```yaml
> apiVersion: operators.coreos.com/v1alpha1
> kind: Subscription
> metadata:
>   name: grafana-operator
>   namespace: keycloak
> spec:
>   channel: v5
>   name: grafana-operator
>   source: community-operators
>   sourceNamespace: openshift-marketplace
> ```

### 2.2 Émetteur de certificat (ClusterIssuer)

Un **`ClusterIssuer` nommé `letsencrypt-prod`** doit exister et être pleinement
configuré (solveur ACME HTTP-01 ou DNS-01 fonctionnel). La ressource
`Certificate` du projet y fait référence pour produire le secret
`keycloak-tls-secret`.

Exemple minimal de `ClusterIssuer` HTTP-01 (à adapter — **non fourni par ce
dépôt**) :

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@exemple.gouv.qc.ca
    privateKeySecretRef:
      name: letsencrypt-prod-account-key
    solvers:
      - http01:
          ingress:
            ingressClassName: openshift-default
```

Vérification : `oc get clusterissuer letsencrypt-prod` doit afficher `READY=True`.

### 2.3 DNS public

Le nom d'hôte de Keycloak (p. ex. `keycloak.apps.sno.myocp.net`) doit **résoudre
publiquement** et router vers l'ingress du cluster, sinon le défi Let's Encrypt
échoue et Keycloak (hostname strict) refuse les requêtes.

### 2.4 Identifiants `registry.redhat.io`

La tâche `buildah` télécharge l'image de base
`registry.redhat.io/rhbk/keycloak-rhel9:26.4`, qui exige une authentification.
Voir l'étape d'amorçage 3.3.

### 2.5 Outils et accès

- `oc` (connecté avec un compte **cluster-admin** pour l'amorçage) ;
- accès en écriture à un fork de ce dépôt (pour adapter le domaine et brancher
  le webhook).

---

## 3. Installation

> Les étapes d'amorçage 3.1 à 3.4 sont des opérations **hors bande** réalisées
> **une seule fois** par un administrateur du cluster, car Argo CD ne peut pas
> s'auto-attribuer de droits ni gérer de secrets en clair.

### 3.0 Adapter la configuration au cluster

Le **socle (`gitops/base`) est générique** ; les valeurs propres à
l'environnement sont définies dans l'**overlay de production**
[`gitops/overlays/production/kustomization.yaml`](gitops/overlays/production/kustomization.yaml).

Remplacer le domaine et, au besoin, le nombre d'instances :

```yaml
patches:
  - target: { group: k8s.keycloak.org, version: v2alpha1, kind: Keycloak, name: keycloak }
    patch: |-
      - op: replace
        path: /spec/hostname/hostname
        value: keycloak.apps.VOTRE-CLUSTER.example.com   # ← votre domaine
      - op: replace
        path: /spec/instances
        value: 1                                          # 1 pour SNO, ≥2 pour la HA
  - target: { group: cert-manager.io, version: v1, kind: Certificate, name: keycloak-tls }
    patch: |-
      - op: replace
        path: /spec/dnsNames/0
        value: keycloak.apps.VOTRE-CLUSTER.example.com   # ← doit être identique au hostname
```

> Le **nom DNS du certificat doit être identique au `hostname` de Keycloak.**

Adapter aussi, si vous utilisez votre propre fork, le `repoURL` dans
[`gitops/argocd/application.yaml`](gitops/argocd/application.yaml).

### 3.1 Santé des PVC dans Argo CD

Les PVC en `WaitForFirstConsumer` restent `Pending` tant qu'aucun pod ne les
monte ; sans personnalisation, Argo CD les juge non sains et bloque la
synchronisation. Appliquer le correctif sur `argocd-cm` :

```bash
oc patch configmap argocd-cm -n openshift-gitops \
  --type=merge \
  --patch-file gitops/argocd/openshift-gitops-patch.yaml
```

### 3.2 Droits de l'instance Argo CD par défaut

L'instance `openshift-gitops` par défaut n'a pas les droits de gérer les
ressources de l'espace `keycloak` (Secrets, `Keycloak` CR, RBAC, etc.). Comme
l'Application utilise `ServerSideApply`, chaque synchronisation est un PATCH
côté serveur qui échoue sans ces droits :

```bash
oc apply -f gitops/argocd/argocd-rbac.yaml
```

### 3.3 Authentification au registre Red Hat (pour `buildah`)

Réutiliser le pull-secret global du cluster et le rattacher au compte de
service `pipeline` (Tekton fusionnera ces identifiants avec ceux du registre
interne) :

```bash
oc get secret/pull-secret -n openshift-config \
  -o go-template='{{index .data ".dockerconfigjson" | base64decode}}' \
  > /tmp/global-pull-secret.json

oc create secret generic redhat-registry \
  --type=kubernetes.io/dockerconfigjson \
  --from-file=.dockerconfigjson=/tmp/global-pull-secret.json \
  -n keycloak

oc secrets link pipeline redhat-registry -n keycloak --for=mount
rm -f /tmp/global-pull-secret.json
```

Détails et variante (compte de service de registre dédié) :
[`gitops/base/pipeline/registry-auth-template.yaml`](gitops/base/pipeline/registry-auth-template.yaml).

> Le compte de service `pipeline` est créé par l'opérateur Pipelines (et aussi
> déclaré dans [`serviceaccount.yaml`](gitops/base/pipeline/serviceaccount.yaml)).
> Si Argo CD ne l'a pas encore créé, faites cette étape **après** la première
> synchronisation (3.5).

### 3.4 Secret de webhook GitHub (déclenchement du pipeline)

L'`EventListener` valide la signature GitHub à l'aide d'un secret :

```bash
oc create secret generic github-webhook-secret \
  --from-literal=secret='UN-SECRET-PARTAGE-ALEATOIRE' \
  -n keycloak
```

Après la synchronisation (3.5), récupérer l'URL publique du webhook et la
configurer dans GitHub (**Settings → Webhooks**, type `application/json`,
événement *push*, même secret) :

```bash
oc get route keycloak-github-webhook -n keycloak -o jsonpath='https://{.spec.host}{"\n"}'
```

### 3.5 Déployer l'Application Argo CD

L'Application Argo CD se trouve hors du chemin synchronisé : elle s'applique
manuellement.

```bash
oc apply -f gitops/argocd/application.yaml
```

Argo CD déploie alors, par vagues de synchronisation (voir §6) :
l'espace de noms, PostgreSQL, le secret BD, le certificat, l'instance Keycloak,
le pipeline et ses déclencheurs, puis l'import du royaume `quebec`.

![argocd_keycloak](/images/gitops.png)


Suivi :

```bash
oc get application rhbk-keycloak -n openshift-gitops \
  -o jsonpath='SYNC={.status.sync.status} HEALTH={.status.health.status}{"\n"}'
argocd app wait rhbk-keycloak    # si la CLI argocd est disponible
```

### 3.6 Remplacer le secret de base de données

[`secrets-template.yaml`](gitops/base/keycloak/secrets-template.yaml) crée
`keycloak-db-secret` avec un **mot de passe de remplacement**. En production,
utiliser **Sealed Secrets** ou **External Secrets Operator** et remplacer ce
gabarit. Ne jamais versionner de secret en clair (le `.gitignore` bloque déjà
les fichiers `*secret*.yaml`).

### 3.7 Première construction de l'image

L'instance `Keycloak` référence l'image
`image-registry.openshift-image-registry.svc:5000/keycloak/keycloak-custom:latest`,
qui doit d'abord être construite par le pipeline. Déclencher une exécution :

```bash
# Soit via un push Git (webhook), soit manuellement ou dans le UI:
tkn pipeline start keycloak-build-deploy -n keycloak \
  -w name=source,claimName=workspace-pvc
```

![build_deploy_pipeline](/images/tekton.png)

Le pipeline compile le thème + l'action requise, construit et pousse l'image,
puis met à jour le CR `Keycloak`. Suivi : `tkn pipelinerun logs -f -n keycloak`.

---

## 4. Démonstration avec le royaume `quebec`

Le royaume d'exemple [`realm-quebec.yaml`](gitops/base/keycloak/realm-quebec.yaml)
est importé automatiquement par l'opérateur. Il active :

- `loginTheme: quebec` — le **thème de connexion personnalisé** ;
- l'action requise **`accepter-conditions-utilisation`** comme **action par
  défaut** (tout nouvel utilisateur doit l'exécuter) ;
- l'**inscription en libre-service** (aucun identifiant versionné) et le
  français par défaut.

Pour tester, l'URL suivant peut être utiliser: https://keycloak.DOMAINE/auth/realms/quebec/account/
et puis créer un compte.

### Éprouver le flux

1. Ouvrir la page de connexion du royaume :
   `https://VOTRE-DOMAINE/auth/realms/quebec/account`
2. Cliquer sur **« S'inscrire »** → le **thème québécois** s'affiche.
3. Compléter l'inscription → l'action requise **« Accepter les conditions
   d'utilisation »** (gabarit `accepter-conditions.ftl` du thème) apparaît.
4. Accepter → accès à la console de compte.

> Pour déclencher l'action sur un utilisateur **existant** : Console
> d'administration → royaume `quebec` → *Users* → (utilisateur) → *Required
> actions* → *Accepter les conditions d'utilisation*.

Identifiants administrateur initiaux (royaume `master`) :

```bash
oc get secret keycloak-initial-admin -n keycloak \
  -o go-template='{{"utilisateur: "}}{{.data.username|base64decode}}{{"\nmot de passe: "}}{{.data.password|base64decode}}{{"\n"}}'
```

---

## 5. Structure du dépôt

```
container/Containerfile           Image RHBK 26.4 optimisée (multi-étapes)
pom.xml                           Projet Maven parent
theme/                            Module Maven : thème de connexion « quebec »
required-action/                  Module Maven : action requise « accepter-conditions »
gitops/
  argocd/
    application.yaml              Application Argo CD (→ overlays/production)
    argocd-rbac.yaml              Amorçage : droits de l'instance GitOps (§3.2)
    openshift-gitops-patch.yaml   Amorçage : santé des PVC (§3.1)
  base/
    namespace.yaml
    keycloak/                     PostgreSQL, Keycloak CR, Certificate, RealmImport, secret (gabarit)
    pipeline/                     SA + RBAC, ImageStream, PVC, Pipeline, déclencheurs
    monitoring/                   ServiceMonitor Keycloak + Grafana (CR, source, tableaux de bord) — §9
  overlays/
    production/                   Surcharge : domaine, nb d'instances, étiquette d'environnement
uwm.yaml                          Amorçage : active UserWorkloadMonitoring (§9.1)
```

---

## 6. Référence — vagues de synchronisation Argo CD

| Vague | Ressources |
|------:|------------|
| `-10` | Espace de noms `keycloak` |
| `-3`  | Secret BD, `Certificate` (cert-manager) |
| `0`/`1` | Compte de service + RBAC, ImageStream, `workspace-pvc` |
| `2`   | Pipeline Tekton et tâches |
| `5`   | Instance `Keycloak` |
| `6`   | `Service` métriques + `ServiceMonitor` Keycloak (§9.2) |
| `10`  | `KeycloakRealmImport` quebec (après que Keycloak soit prêt) |
| `14`  | RBAC Grafana (SA, jeton, `cluster-monitoring-view`), secret admin (§9.3) |
| `15`  | Instance `Grafana` + `Route` |
| `16`  | `GrafanaDatasource` (Thanos) + `GrafanaDashboard` (×2) |

---

## 7. Vérification et dépannage

```bash
# État global
oc get pods -n keycloak
oc get keycloak keycloak -n keycloak -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'

# Certificat TLS
oc get certificate keycloak-tls -n keycloak
oc describe certificate keycloak-tls -n keycloak     # voir les Events si bloqué

# Import du royaume
oc get keycloakrealmimport quebec-realm -n keycloak -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'

# Pipeline
tkn pipelinerun list -n keycloak
tkn pipelinerun logs -f -n keycloak
```

Points d'attention fréquents :

- **`buildah` : `unauthorized` sur registry.redhat.io** → étape 3.3 non faite
  (secret non rattaché au SA `pipeline`).
- **Keycloak en `CrashLoopBackOff` après changement d'option de *build*** (p. ex.
  `http-relative-path`) → reconstruire l'image (option intégrée à l'image, pas
  d'effet à l'exécution avec `startOptimized: true`).
- **`Certificate` qui n'est jamais `Ready`** → DNS public ou solveur du
  `ClusterIssuer` non fonctionnel (§2.2 et §2.3).
- **Modification du thème sans effet** → le thème est intégré à l'image ;
  relancer le pipeline (§3.7).
- **Toute modification de `application.yaml`** → ré-appliquer avec
  `oc apply -f gitops/argocd/application.yaml` (hors du chemin synchronisé).

---

## 8. Personnalisations incluses

- **Thème** ([`theme/`](theme/)) — gabarit de connexion sombre conforme au
  système de design Québec.ca, ciblant le markup historique de Keycloak
  (`login-pf` / PatternFly `pf-c-*`).
- **Action requise** ([`required-action/`](required-action/)) — fournisseur
  `accepter-conditions-utilisation` qui affiche `accepter-conditions.ftl` et
  exige un clic d'acceptation avant l'accès.

---

## 9. Observabilité — monitoring et Grafana

Cette section met en place une chaîne de bout en bout :

```
Keycloak (/metrics, port 9000)
   │  scrape (ServiceMonitor)
   ▼
Prometheus user-workload-monitoring  ──►  Thanos Querier (openshift-monitoring)
                                              │  requêtes PromQL (jeton SA, port 9091)
                                              ▼
                                           Grafana  ◄── tableaux de bord Keycloak officiels
```

Les manifestes vivent dans [`gitops/base/monitoring/`](gitops/base/monitoring/)
et sont synchronisés par Argo CD. **Seule l'activation de
UserWorkloadMonitoring (§9.1) est une opération d'amorçage hors bande**, car
elle modifie une `ConfigMap` de l'espace de noms `openshift-monitoring`.

> Note : `gitops/base/monitoring/` est référencé depuis **l'overlay** et non
> depuis `base/kustomization.yaml`. Ce dernier utilise `commonLabels`, qui
> injecte ses étiquettes dans les **sélecteurs** ; le `Service` `keycloak-metrics`
> cible des pods gérés par l'opérateur (étiquette `app=keycloak`, sans
> `managed-by=argocd`). L'overlay (`labels` + `includeSelectors: false`)
> préserve donc le sélecteur.

### 9.1 Activer UserWorkloadMonitoring (OpenShift 4.21)

OpenShift surveille par défaut **uniquement** les composants de la plateforme.
Pour scraper les projets utilisateur (dont `keycloak`), activez le **User
Workload Monitoring** via la `ConfigMap` `cluster-monitoring-config` :

```bash
oc apply -f uwm.yaml
```

[`uwm.yaml`](uwm.yaml) positionne `enableUserWorkload: true`. Vérification :

```bash
oc -n openshift-user-workload-monitoring get pods
# prometheus-user-workload-* et prometheus-operator-* doivent être Running
```

> ⚠️ L'espace de noms `keycloak` **ne doit pas** porter l'étiquette
> `openshift.io/cluster-monitoring: "true"` ([`namespace.yaml`](gitops/base/namespace.yaml)).
> Cette étiquette rattache l'espace de noms au monitoring de **plateforme**
> (`prometheus-k8s`) et l'**exclut** du User Workload Monitoring : le
> `ServiceMonitor` ne serait alors scrapé par personne (cible absente de
> *Observe → Targets*). UWM surveille automatiquement les projets utilisateur
> qui ne portent **pas** cette étiquette ; aucune étiquette n'est requise.

### 9.2 Métriques Keycloak et `ServiceMonitor`

Les options de **build** `metrics-enabled`, `health-enabled` et
`event-metrics-user-enabled` sont intégrées à l'**image**
([`container/Containerfile`](container/Containerfile)). Les métriques sont
exposées sur l'**interface de gestion** (port `9000`, chemin `/metrics`),
distincte du port applicatif et **non** affectée par `http-relative-path`.

> ⚠️ Les options de **build** ne doivent **pas** figurer dans `additionalOptions`
> du CR : avec `startOptimized: true` l'opérateur ne relance pas `kc.sh build`,
> et Keycloak refuse alors de démarrer (« *build time options have values that
> differ from what is persisted* »). Toute modification (p. ex. activer
> `event-metrics-user-enabled`) exige donc une **reconstruction de l'image**
> (relancer le pipeline, §3.7).

Le CR Keycloak ([`keycloak.yaml`](gitops/base/keycloak/keycloak.yaml)) n'ajoute
qu'une option d'**exécution** (effective malgré `startOptimized: true`) :

| Option | Type | Tableau de bord concerné |
|--------|------|--------------------------|
| `http-metrics-histograms-enabled=true` | exécution (CR) | *Troubleshooting* (cartes de latence) |
| `event-metrics-user-enabled=true` | **build** (image) | *Capacity planning* (connexions, inscriptions…) |

Depuis **RHBK 26.4**, l'opérateur crée automatiquement un `ServiceMonitor`
lorsque les métriques sont actives. Ce dépôt fournit **son propre
`ServiceMonitor` déclaratif** et désactive donc celui de l'opérateur
(`spec.serviceMonitor.enabled: false`) pour éviter un double scraping :

- [`keycloak-metrics-service.yaml`](gitops/base/monitoring/keycloak-metrics-service.yaml)
  — `Service` exposant le port `management` (9000), car le `Service` de
  l'opérateur n'expose que 8443/8080 ;
- [`keycloak-servicemonitor.yaml`](gitops/base/monitoring/keycloak-servicemonitor.yaml)
  — scrape `https://…:9000/metrics` toutes les 30 s (`insecureSkipVerify` car
  l'interface de gestion sert le certificat interne).

Vérification :

```bash
oc -n keycloak get servicemonitor keycloak
# Cibles « up » dans Prometheus :
oc -n openshift-user-workload-monitoring exec -it sts/prometheus-user-workload -- \
  wget -qO- http://localhost:9090/api/v1/targets | grep keycloak
```

### 9.3 Déployer Grafana et la source de données

Le **Grafana Operator** (§2.1) doit être installé. Les ressources :

- [`grafana.yaml`](gitops/base/monitoring/grafana.yaml) — instance `Grafana`
  (étiquette `dashboards: grafana`, cible des CR source/dashboards). Identifiants
  admin injectés depuis le secret `grafana-admin-credentials` ;
- [`grafana-route.yaml`](gitops/base/monitoring/grafana-route.yaml) — `Route`
  HTTPS (terminaison edge) vers `keycloak-grafana-service:3000` ;
- [`grafana-rbac.yaml`](gitops/base/monitoring/grafana-rbac.yaml) — compte de
  service `grafana-sa`, liaison au `ClusterRole` **`cluster-monitoring-view`** et
  `Secret` de jeton (requis depuis OpenShift 4.11) ;
- [`grafana-datasource.yaml`](gitops/base/monitoring/grafana-datasource.yaml) —
  source `Prometheus` pointant vers le **Thanos Querier**
  (`thanos-querier.openshift-monitoring.svc:9091`). Le jeton `grafana-sa` est
  injecté dans l'en-tête `Authorization` (`valuesFrom`).

> **Avant la synchronisation**, remplacez le gabarit
> [`grafana-secret-template.yaml`](gitops/base/monitoring/grafana-secret-template.yaml)
> par un secret réel (SealedSecrets/External Secrets) — comme pour le secret BD
> (§3.6) — sinon le mot de passe admin reste la valeur d'exemple.

Thanos Querier sur le port `9091` applique le RBAC Kubernetes : sans
`cluster-monitoring-view`, Grafana reçoit `403` sur ses requêtes.

### 9.4 Tableaux de bord Keycloak

[`grafana-dashboards.yaml`](gitops/base/monitoring/grafana-dashboards.yaml)
importe les **tableaux de bord officiels** depuis
<https://github.com/keycloak/keycloak-grafana-dashboard> (l'opérateur télécharge
le JSON à l'URL indiquée) :

| Tableau de bord | Usage |
|-----------------|-------|
| `keycloak-capacity-planning` | Dimensionnement (charge, événements utilisateur) |
| `keycloak-troubleshooting` | Diagnostic (latences, erreurs, JVM, cache) |

L'entrée `__inputs` `DS_PROMETHEUS` de chaque tableau de bord est reliée à la
source `Prometheus` via le champ `datasources` du CR `GrafanaDashboard`.

### 9.5 Accès et vérification

```bash
# URL de Grafana
oc -n keycloak get route keycloak-grafana -o jsonpath='{.spec.host}{"\n"}'

# État des ressources Grafana
oc -n keycloak get grafana,grafanadatasource,grafanadashboard

# Le pod Grafana doit être Running
oc -n keycloak get pods -l app.kubernetes.io/managed-by=grafana-operator
```

Connectez-vous avec les identifiants du secret `grafana-admin-credentials`,
puis ouvrez les tableaux de bord *Keycloak capacity planning* et *Keycloak
troubleshooting*. Si les graphiques sont vides, vérifier dans l'ordre : UWM
actif (§9.1) → cible `keycloak` « up » (§9.2) → source de données Grafana
« working » (jeton/RBAC §9.3).
