# Payload Templates

Each worker defines their own payload template schema. Please see the navigation on the left to find the respective worker's payload template schema.

## Base Template
All worker ships will have the following fields:

```yaml
TemplateName: SomeNameForYourTemplate
TemplateDescription: Some description that makes it easy for you to understand what this is for.
```

Each worker ship then defines additional fields as appropriate.

## Account and Account Region Payload Reference
The schemas for the Account and Account/Region worker ship payloads [can be found here](../architecture/PayloadTemplates.md#account-worker-templates).