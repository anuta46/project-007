from django.contrib.auth.tokens import PasswordResetTokenGenerator
# IMPORTANT: The 'six' module is not used in modern Django and should NOT be imported.
# If you see 'from django.utils import six', please remove that line.

# This token generator can be used for things like account activation
# or password reset links, ensuring the link is used only once and expires.
class AccountActivationTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        # We're combining user's primary key, their active status,
        # and the timestamp to create a unique hash for the token.
        # This means if their active status changes or the token expires,
        # the old token becomes invalid.
        return (
            str(user.pk) + str(user.is_active) + str(timestamp)
        )

# Create an instance of the token generator
account_activation_token = AccountActivationTokenGenerator()
