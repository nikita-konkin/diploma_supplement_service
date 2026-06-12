package edu.university.xlsxpivot;

import org.junit.Test;

import static org.hamcrest.CoreMatchers.is;
import static org.junit.Assert.assertThat;

public final class DownstreamServiceExceptionTest {

    @Test
    public void cannotDiscardJsonDetail() {
        final DownstreamServiceException error = DownstreamServiceException.from(
            500,
            "{\"detail\":\"None of ['Дисциплины'] are in the columns\"}",
            "XML service"
        );
        assertThat(
            "Gateway discarded the useful Python failure",
            error.status() + ":" + error.getMessage(),
            is("500:None of ['Дисциплины'] are in the columns")
        );
    }

    @Test
    public void cannotInventEmptyFailure() {
        assertThat(
            "Gateway returned an empty downstream failure",
            DownstreamServiceException.from(503, "", "XML service").getMessage(),
            is("XML service returned HTTP 503")
        );
    }
}
