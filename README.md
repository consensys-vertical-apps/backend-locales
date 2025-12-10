# backend-locales

## Intro and rationale
This repository contains localization files for MetaMask backend services, such as notifications.

The files are json files with a flat dictionary structure with no nested keys.
Names get a bit long, but it's easier to manage. Example:

```json
  "pushPlatformNotificationsFundsReceivedTitle": {
    "message": "Funds received"
  },
  "pushPlatformNotificationsFundsReceivedDescription": {
    "message": "You received $1 $2"
  },
```

## Namespace and structure
Please make sure your keys are namespaced with your project name to avoid collisions and keep things tidy.
Example:
```
<namespace><ProjectName><Action><Type>

pushNotificationShieldClaimCreatedTitle
```

If you need different copies for different platforms (mobile, extension), please suffix the keys accordingly:

```json
  "pushSomeKeyMobile": {
    "message": "Transaction Speeded Up"
  },
  "pushSomeKeyExtension": {
    "message": "Transaction Speeded Up"
  }
```

## Placeholders
Placeholders (`$1`, `$2`, etc.) are used for dynamic content - so the backend can replace them with actual values.
Example:
```json
  "pushPlatformNotificationsFundsReceivedDescription": {
    "message": "You received $1 $2"
  },
```

at runtime becomes: `You received 0.5 ETH`.

## Additional metadata
Keys can have additional metadata, such as `description` to provide context for translators. Example:

```json
  "pushNotificationLimitOrderFilledDescriptionLong": {
    "message": "Your $1 long position is now open.",
    "description": "$1 is the asset symbol"
  }
```

## Contributing new keys
Create a PR and add your new keys to the `en/messages.json` file.
The translation team will take care of propagating them to other locales.