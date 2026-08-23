# Annadata Setu — Digital Public Good Schemas

Open data standards for a farmer-sourced crop-disease surveillance system. Apache 2.0
(see [`LICENSE`](./LICENSE)). Fork them, extend them, run your own instance.

## The four schemas

| File | Describes | Classes |
|---|---|---|
| [`plot-passport.v1.jsonld`](./plot-passport.v1.jsonld) | Everything known about one plot, derived from its coordinates alone | `PlotPassport`, `NdviSample`, `SoilProfile`, `WeatherForecast` |
| [`advisory-event.v1.jsonld`](./advisory-event.v1.jsonld) | One diagnosis delivered to one farmer | `AdvisoryEvent` |
| [`disease-observation.v1.jsonld`](./disease-observation.v1.jsonld) | The epidemiological layer: individual reports and the clusters derived from them | `DiseaseObservation`, `Outbreak` |
| [`model-registry.v1.jsonld`](./model-registry.v1.jsonld) | Published model lineage and measured performance | `ModelRegistryEntry` |

[`sample-dataset.json`](./sample-dataset.json) is a worked example of all five record
types, generated from a live instance rather than written by hand.

## Namespace

All terms live under:

```
https://perzival07.github.io/Annadata-Setu/ns/v1#
```

Each `.jsonld` file is both a **vocabulary definition** and a usable **`@context`**.
Point your instance data at it and the snake_case field names resolve to IRIs directly:

```json
{
  "@context": "https://perzival07.github.io/Annadata-Setu/schema/plot-passport.v1.jsonld",
  "@type": "PlotPassport",
  "plot_id": "hash_24aebeab",
  "geohash": "tes3z0k",
  "inferred_crop": "Tomato",
  "crop_stage_days": 58
}
```

Standard vocabularies are reused where they exist rather than reinvented: coordinates
are `geo:lat` / `geo:long` (WGS84), timestamps are `dcterms:created` / `dcterms:modified`.

## Conformance rules

These are the constraints a conforming implementation must honour. They are carried in
each schema as `as:constraint` annotations, and they are not stylistic.

**1. An outbreak is never published below the k-anonymity threshold.**
`Outbreak` records require `report_count >= 5` **and** `distinct_plots >= 3`. Enforce
this in the query that builds the cluster, not as a filter in a user interface — a
cluster that was never assembled cannot leak. The `distinct_plots` floor exists so that
repeat reports from a single plot cannot manufacture an outbreak.

**2. `escalate_to_human` is a third outcome, and it is resolved first.**
An `AdvisoryEvent` has three states, not two:

| State | `escalate_to_human` | `is_action_needed` | Meaning |
|---|---|---|---|
| Treat | `false` | `true` | A condition was identified and a treatment is prescribed |
| Don't spray | `false` | `false` | Abiotic or benign — chemical treatment would waste money |
| Undetermined | `true` | *(ignore)* | No reliable answer; a human agronomist must review |

A renderer that branches on `is_action_needed` without first checking
`escalate_to_human` will present an unresolved diagnosis as an all-clear to a farmer
whose crop may be actively infected. Check `escalate_to_human` first.

**3. `escalate_to_human` must be true whenever `confidence < 0.65`**, regardless of what
the model itself reported. Enforce the threshold in your own code.

**4. An escalated advisory carries no prescription.** `dosage` must be `null` and
`estimated_cost_inr` must be `0`. This is defence in depth for rule 2: a consumer that
gets the branching wrong still finds nothing to bill the farmer for.

**5. `dosage` is null unless a cited source specifies it.** If your retrieved references
do not state an application rate, say so in `action_text` and leave `dosage` null. Never
synthesise one.

**6. `data_sources` and `sources` are mandatory.** An advisory that cannot name its
provenance cannot be audited by the administration adopting it.

**7. Observations are undated at their peril.** `created_at` is required on
`DiseaseObservation`. Clustering runs over a rolling 7-day window; an undated report
cannot support a claim that something is happening *now*, and should be excluded.

## A note on `null` in JSON-LD

JSON-LD treats `"dosage": null` as equivalent to omitting the key, so the distinction
between *"explicitly no dosage"* and *"not stated"* does not survive expansion to RDF.
That distinction is recoverable from `escalate_to_human` and `is_action_needed`, which
are always present — consumers working at the RDF level should read those rather than
inferring meaning from an absent `dosage`.

## Adopting this in another region

1. **Keep the field names.** They are snake_case in the JSON and in the API. Changing
   them forks the vocabulary and breaks the shared clustering and alerting semantics.
2. **Extend, don't edit.** Add region-specific terms under your own namespace and
   reference both contexts:
   ```json
   "@context": [
     "https://perzival07.github.io/Annadata-Setu/schema/plot-passport.v1.jsonld",
     {"ka": "https://example.karnataka.gov.in/ns/v1#", "taluk": "ka:taluk"}
   ]
   ```
3. **Record your fork in the model registry.** `fork_lineage` is an ordered ancestry.
   A model tuned for a new region should name the model it descended from, so a claim
   of "we forked their tomato model" is checkable rather than asserted.
4. **Publish `calibration_error` alongside `accuracy_f1`.** A confidence threshold
   governs escalation, so a well-ranked but poorly calibrated model escalates the wrong
   cases. F1 alone does not tell an adopter whether the escalation rule will behave.

## Versioning

Filenames carry the major version (`.v1.`). Additive changes — new optional properties —
ship within `v1`. Removing or retyping a property requires `v2`, published alongside `v1`
rather than replacing it.
