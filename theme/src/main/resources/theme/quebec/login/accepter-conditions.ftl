<#import "template.ftl" as layout>
<@layout.registrationLayout displayInfo=false displayMessage=!messagesPerField.existsError('general'); section>
    <#if section = "header">
        ${msg("accepterConditionsTitre")}
    <#elseif section = "form">
        <div class="gq-conditions-wrapper">
            <#if message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
                <div class="pf-c-alert pf-m-${message.type} pf-m-inline" aria-live="polite">
                    <div class="pf-c-alert__icon">
                        <i class="fas fa-info-circle" aria-hidden="true"></i>
                    </div>
                    <p class="pf-c-alert__title">${kcSanitize(message.summary)?no_esc}</p>
                </div>
            </#if>

            <p class="gq-conditions-soustitre">
                ${msg("accepterConditionsSousTitre")}
            </p>

            <div class="gq-conditions-texte">
                <p>${msg("accepterConditionsTexte")}</p>
            </div>

            <form id="kc-accepter-conditions-form"
                  class="${properties.kcFormClass!}"
                  action="${url.loginAction}"
                  method="post">

                <div class="${properties.kcFormGroupClass!}">
                    <div id="kc-form-buttons" class="${properties.kcFormButtonsClass!}">
                        <button class="gq-conditions-accepter-btn ${properties.kcButtonClass!} ${properties.kcButtonPrimaryClass!} ${properties.kcButtonBlockClass!} ${properties.kcButtonLargeClass!}"
                                type="submit"
                                name="submit"
                                value="accepter">
                            ${msg("accepterConditionsBouton")}
                        </button>
                    </div>
                </div>
            </form>
        </div>
    </#if>
</@layout.registrationLayout>
