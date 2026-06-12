package edu.university.xlsxpivot;

import org.junit.Test;
import org.takes.rs.RsPrint;

import static org.hamcrest.CoreMatchers.is;
import static org.junit.Assert.assertThat;

public final class ApiResponseTest {

    @Test
    public void cannotProduceBrokenJson() throws Exception {
        assertThat(
            "Gateway produced invalid JSON for a quoted error",
            new RsPrint(ApiResponse.error(500, "Missing \"Дисциплины\"")).printBody(),
            is("{\"error\":\"Missing \\\"Дисциплины\\\"\",\"status\":500}")
        );
    }
}
