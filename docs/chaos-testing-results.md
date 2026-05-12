# Chaos Testing Results

## Scenario 1: Pod Failure (Self-Healing)

**Action:** `kubectl delete pod` on running argus-api pod

**Expected:** Kubernetes recreates the pod automatically

**Result:**
- Old pod terminated immediately
- New pod created within 1-2 seconds
- Pod reached Running state in ~15 seconds
- Application responded to requests after recreation
- Image pulled: satvik55/argus-api:stable-clean (1.188s)
- ArgoCD showed no drift (pod is managed by ReplicaSet)

**Recovery Time:** ~15 seconds (11:37:35 → 11:37:52)

---

## Scenario 2: Error Spike (Bad Deploy)

**Action:** Deployed code with 50% error rate on `/api/items` via full CI/CD pipeline

**Expected:** Detector catches error rate anomaly, identifies as application-level issue

**Result:**
- 50% of requests returned HTTP 500
- ArgoCD self-heal kept reverting manual fixes (GitOps working as designed)
- Fix required pushing corrected image tag through Git
- Detector identified anomaly with root-cause:
  "Error rate elevated without resource pressure → Application-level issue"

**Detection Time:** ~2-4 minutes after deployment

**Key Insight:** In a GitOps workflow, `kubectl set image` is temporary — ArgoCD reverts it. The only permanent fix is through Git.

---

## Scenario 3: Sustained CPU Stress

**Action:** Hit `/api/stress?duration=25` repeatedly for ~2 minutes

**Expected:** Detector catches CPU anomaly without request rate increase

**Result:**
- CPU spiked on the stressed pod (4 bursts over ~2 minutes)
- Request rate remained stable (only background traffic)
- Detector analyzed metrics and correlated CPU vs request patterns

**Detection Time:** ~2-4 minutes

**Key Insight:** Detector correctly distinguished between load-driven CPU (Day 10) and non-load CPU (this scenario), providing different root-cause recommendations.

---

## Summary

| Scenario | Trigger | Detected? | Root-Cause Accurate? | Recovery |
|----------|---------|-----------|---------------------|----------|
| Pod Failure | kubectl delete pod | Restart count +1 | N/A | ~15s auto-heal |
| Error Spike | Bad code deploy (50% 500s) | ✅ Error rate anomaly | ✅ "App-level issue" | GitOps revert |
| CPU Stress | /api/stress endpoint | ✅ CPU anomaly | ✅ "Background process" | Self-resolved |

---

## Challenges & Debugging During Chaos Testing

### 1. ArgoCD vs Manual kubectl — The Core Lesson

**Problem:** After reverting the chaos code locally and rebuilding the image, `kubectl set image` was used to update the deployment. ArgoCD immediately reverted it back to `chaos-v3` (the tag in Git).

**Why:** ArgoCD self-heal compares cluster state to Git state every 3 minutes. Any manual kubectl change is treated as drift and overwritten.

**Diagnosis:** `kubectl get pods -o jsonpath='{.items[0].spec.containers[0].image}'` revealed the pod was still running `chaos-v3` despite successful rollout status.

**Fix:** Updated `values.yaml` in Git → pushed → deleted/recreated ArgoCD Application → ArgoCD synced `stable-clean` from Git.

**Takeaway:** In GitOps, the cluster is a reflection of Git. You cannot fix deployments bypassing Git.

### 2. Docker Build Unicode Dash

**Problem:** Copy-pasted `docker buildx build` commands contained unicode dashes instead of ASCII dashes (`--`).

**Fix:** Retyped commands manually with correct `--platform` flag.

### 3. Z-Score Edge Case

**Problem:** Latency Z-score computed as `3913965742944.19` — mathematically valid but meaningless.

**Cause:** Near-zero standard deviation in the rolling window caused extreme division result.

**Takeaway:** Future improvement — add a minimum stddev floor to prevent extreme Z-scores.

### 4. Grafana Annotation 401

**Problem:** Detector logged annotation creation failed with 401 Unauthorized.

**Cause:** API key secret was lost during an ArgoCD re-sync (secret value was empty in Git).

**Fix:** Recreated the Grafana Service Account token and patched the K8s Secret.

### 5. Rollout Success ≠ App Healthy

**Problem:** `kubectl rollout status` reported success, but app still returned 500 errors.

**Cause:** Kubernetes health checks verify container liveness (process running), not business logic. The chaos code passed health checks because `/health` was fine — only `/api/items` returned errors.

**Takeaway:** Rollout status checks pod health, not application correctness. Separate readiness from business logic validation.

---

## Key Observations

1. **Kubernetes self-healing** restores pods in <15 seconds
2. **ArgoCD GitOps** prevents manual drift — the only permanent fix is through Git
3. **Anomaly detector** correctly correlates metrics to distinguish failure types
4. **Z-score threshold of 2.5** catches real anomalies, avoids false positives
5. **Debugging in GitOps** requires understanding that the cluster is read-only — Git is the source of truth
