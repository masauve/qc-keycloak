package ca.quebec.gouv.keycloak.action;

import jakarta.ws.rs.core.Response;
import org.keycloak.authentication.RequiredActionContext;
import org.keycloak.authentication.RequiredActionProvider;

/**
 * Action requise : l'utilisateur doit cliquer sur un bouton d'acceptation
 * des conditions d'utilisation avant de pouvoir accéder aux services.
 *
 * Le gabarit FreeMarker "accepter-conditions.ftl" doit être présent dans
 * le thème de connexion actif du royaume (ex: quebec).
 */
public class AccepterConditionsAction implements RequiredActionProvider {

    @Override
    public void evaluateTriggers(RequiredActionContext context) {
        // L'action est déclenchée manuellement par l'administrateur ou lors de l'inscription.
        // Aucun déclenchement automatique basé sur des conditions.
    }

    @Override
    public void requiredActionChallenge(RequiredActionContext context) {
        Response challenge = context.form()
                .createForm("accepter-conditions.ftl");
        context.challenge(challenge);
    }

    @Override
    public void processAction(RequiredActionContext context) {
        // L'utilisateur a soumis le formulaire en cliquant sur le bouton d'acceptation.
        // Marquer l'action comme réussie pour continuer le flux d'authentification.
        context.success();
    }

    @Override
    public void close() {
    }
}
