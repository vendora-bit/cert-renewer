# Kubernetes: certificate consumer, not cert-manager replacement

If Kubernetes owns the certificate lifecycle, prefer cert-manager. This pattern
is for a self-hosted service whose certificates are reconciled externally and
then synchronized into a Kubernetes Secret by your existing secret-delivery
system.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: tls-consumer
spec:
  template:
    spec:
      containers:
        - name: app
          image: ghcr.io/example/tls-consumer:stable
          volumeMounts:
            - name: tls
              mountPath: /run/tls
              readOnly: true
      volumes:
        - name: tls
          secret:
            secretName: example-com-tls
```

Keep Cloudflare tokens and ACME state outside the workload. Your synchronizer
should update the Secret only after it has validated the matching certificate
and key from `current/`; then roll or reload consumers according to their own
safe update strategy.

