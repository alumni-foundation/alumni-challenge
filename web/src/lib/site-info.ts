import { HOURS_SHORT } from "./site-content/edits";

/** Contact details as published on the old site (see web/content/old-site/site.json), with one set of opening hours. */
export const contact = {
  address: ["Milestone Business Center", "Kiambu Road"],
  phone: "0104 063 038",
  phoneHref: "tel:0104063038",
  email: "admin@alumnichallenge.foundation",
  hours: [
    { days: "Mon to Fri", time: "08:00 to 17:00" },
    { days: "Sat", time: "09:00 to 12:00" },
  ],
  hoursShort: HOURS_SHORT,
};
