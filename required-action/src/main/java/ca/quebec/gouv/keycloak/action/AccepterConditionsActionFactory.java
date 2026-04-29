package ca.quebec.gouv.keycloak.action;

import org.keycloak.Config;
import org.keycloak.authentication.RequiredActionFactory;
import org.keycloak.authentication.RequiredActionProvider;
import org.keycloak.models.KeycloakSession;
import org.keycloak.models.KeycloakSessionFactory;

public class AccepterConditionsActionFactory implements RequiredActionFactory {

    public static final String PROVIDER_ID = "accepter-conditions-utilisation";

    @Override
    public RequiredActionProvider create(KeycloakSession session) {
        return new AccepterConditionsAction();
    }

    @Override
    public void init(Config.Scope config) {
    }

    @Override
    public void postInit(KeycloakSessionFactory factory) {
    }

    @Override
    public void close() {
    }

    @Override
    public String getId() {
        return PROVIDER_ID;
    }

    @Override
    public String getDisplayText() {
        return "Accepter les conditions d'utilisation";
    }

    @Override
    public boolean isOneTimeAction() {
        return true;
    }
}
